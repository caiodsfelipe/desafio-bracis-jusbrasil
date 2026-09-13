# -*- coding: utf-8 -*-
"""
Chamada ao Qwen3-8B via transformers, para as duas tarefas do pipeline que
usam LLM: extração de citações em prosa livre (prompt_extracao.py) e
classificação dono/citação (prompt_dono.py).

Modelo: Qwen/Qwen3-8B, licença Apache 2.0, commit fixo
b968826d9c46dd6066d109eabc6255188de91218 (ver memória do projeto — decisão
de arquitetura). Requer GPU (envelope de execução do desafio: 24GB VRAM);
não roda de forma viável na máquina de desenvolvimento local (8GB RAM, sem
GPU) — pensado para rodar em Kaggle Notebook.

Sem quantização: em bfloat16, o modelo (8.2B parâmetros) precisa de
~16.4GB — não cabe numa única GPU T4 do Kaggle (~15.6GB), mas cabe com
folga distribuído entre as 2 GPUs T4x2 disponíveis (~31GB no total).
Tentativas anteriores com bitsandbytes 4-bit esbarraram num bug conhecido
e sem correção lançada no transformers v5
(https://github.com/huggingface/transformers/issues/43032), e rebaixar a
versão do transformers para contornar o bug quebra o suporte a Qwen3 (que
exige >= 4.51) — sem versão que sirva para os dois lados. Não usar
bitsandbytes aqui evita o problema por completo: usa a versão de
transformers que o Kaggle já tem por padrão, sem downgrade.

Decodificação determinística (temperature=0 efetivo via greedy decoding,
do_sample=False) — exigência das regras do desafio, para reprodutibilidade.
Thinking mode desligado (enable_thinking=False): a tarefa é extração/
classificação direta, não precisa do raciocínio passo-a-passo do modo
"thinking", que só aumentaria custo de inferência sem ganho aqui.
"""
from dataclasses import dataclass

MODELO_ID = "Qwen/Qwen3-8B"
MODELO_REVISAO = "b968826d9c46dd6066d109eabc6255188de91218"


@dataclass
class RespostaLLM:
    texto: str


class QwenClassificador:
    """Carrega o modelo uma única vez (custo alto) e reusa para todas as
    chamadas do pipeline — nunca recarregar por citação/documento."""

    def __init__(self, device_map: str = "balanced"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODELO_ID, revision=MODELO_REVISAO
        )
        # "balanced" distribui as camadas do modelo entre as GPUs
        # disponíveis (Kaggle T4x2 = 2 GPUs de ~15.6GB) — sem isso
        # ("cuda", uma GPU só), 16.4GB em bfloat16 não cabe em 15.6GB.
        self.model = AutoModelForCausalLM.from_pretrained(
            MODELO_ID,
            revision=MODELO_REVISAO,
            torch_dtype=torch.bfloat16,
            device_map=device_map,
        )
        self.model.eval()

    def _montar_entrada(self, prompt_sistema: str, prompt_usuario: str) -> str:
        return self.tokenizer.apply_chat_template(
            [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    def gerar_lote(
        self,
        prompt_sistema: str,
        prompts_usuario: list[str],
        max_novos_tokens: int = 512,
        tamanho_lote: int = 16,
    ) -> list[RespostaLLM]:
        """Gera respostas para vários prompts numa única passada pela GPU.

        Por que importa: a classificação dono/citação faz uma pergunta por
        candidato e a resposta útil tem 1 token — em série, são dezenas de
        chamadas sequenciais dominadas por overhead, não por computação.
        Em lote, o mesmo trabalho cabe numa passada só.

        Padding à ESQUERDA é obrigatório aqui: em modelo decoder-only, o
        texto gerado continua a partir do último token da sequência: com
        padding à direita a continuação começaria depois do preenchimento,
        produzindo saída inútil para os prompts mais curtos do lote.

        `tamanho_lote` limita quantos prompts vão juntos numa passada: o
        padding iguala todos ao mais longo do lote, então um lote muito
        grande custa memória de GPU proporcional ao pior caso."""
        import torch

        if not prompts_usuario:
            return []

        # com o modelo distribuído entre GPUs, a entrada precisa ir para o
        # device do PRIMEIRO parâmetro, não de "model.device" diretamente
        # (que não é bem definido quando há mais de uma GPU envolvida).
        primeiro_device = next(self.model.parameters()).device
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        respostas: list[RespostaLLM] = []
        for inicio in range(0, len(prompts_usuario), tamanho_lote):
            fatia = prompts_usuario[inicio : inicio + tamanho_lote]
            entradas_texto = [self._montar_entrada(prompt_sistema, p) for p in fatia]

            lado_original = self.tokenizer.padding_side
            self.tokenizer.padding_side = "left"
            try:
                entradas = self.tokenizer(
                    entradas_texto, return_tensors="pt", padding=True
                ).to(primeiro_device)
            finally:
                self.tokenizer.padding_side = lado_original

            with torch.no_grad():
                saida = self.model.generate(
                    **entradas,
                    max_new_tokens=max_novos_tokens,
                    do_sample=False,  # greedy decoding = determinístico (temperature=0 efetivo)
                    temperature=None,
                    top_p=None,
                    top_k=None,
                    pad_token_id=self.tokenizer.pad_token_id,
                )

            tamanho_entrada = entradas["input_ids"].shape[1]
            respostas.extend(
                RespostaLLM(
                    texto=self.tokenizer.decode(
                        sequencia[tamanho_entrada:], skip_special_tokens=True
                    ).strip()
                )
                for sequencia in saida
            )
        return respostas

    def gerar(self, prompt_sistema: str, prompt_usuario: str, max_novos_tokens: int = 512) -> RespostaLLM:
        return self.gerar_lote(prompt_sistema, [prompt_usuario], max_novos_tokens)[0]
