# -*- coding: utf-8 -*-
"""
Interface com o Qwen3-8B para as duas tarefas do pipeline que dependem de
compreensão de texto: a extração de citações em prosa (prompt_extracao.py)
e a classificação de propriedade do processo (prompt_dono.py).

Modelo `Qwen/Qwen3-8B` sob licença Apache 2.0, fixado por revisão. Em
bfloat16 ocupa cerca de 16 GB, distribuídos entre as GPUs disponíveis.

A decodificação é gulosa, sem amostragem, para que a mesma entrada produza
sempre a mesma saída. O modo de raciocínio passo a passo fica desligado:
as duas tarefas são de leitura direta.
"""
from dataclasses import dataclass

MODELO_ID = "Qwen/Qwen3-8B"
MODELO_REVISAO = "b968826d9c46dd6066d109eabc6255188de91218"


@dataclass
class RespostaLLM:
    texto: str


class QwenClassificador:
    """Mantém o modelo carregado para todas as chamadas do pipeline."""

    def __init__(self, device_map: str = "balanced"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODELO_ID, revision=MODELO_REVISAO
        )
        # As camadas são distribuídas entre as GPUs disponíveis; o modelo
        # não cabe numa placa de 16 GB sozinha.
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
        """Respostas para vários prompts, agrupados em passadas pela GPU.

        O preenchimento é aplicado à esquerda porque a geração continua a
        partir do último token da sequência. `tamanho_lote` limita o
        consumo de memória, que acompanha o prompt mais longo do lote.
        """
        import torch

        if not prompts_usuario:
            return []

        # Com o modelo repartido entre GPUs, a entrada acompanha o
        # dispositivo da primeira camada.
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
                    do_sample=False,
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
