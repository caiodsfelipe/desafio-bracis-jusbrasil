"""
Interface com o Qwen3-8B para a única tarefa do pipeline que depende de
compreensão de texto: escolher, entre registros do acervo autuados com o
mesmo número, aquele a que a citação se refere (prompt_dono.py).

Modelo `Qwen/Qwen3-8B` sob licença Apache 2.0, fixado por revisão. Em
bfloat16 ocupa cerca de 16 GB, distribuídos entre as GPUs disponíveis.

A decodificação é gulosa, sem amostragem, para que a mesma entrada produza
sempre a mesma saída. O modo de raciocínio passo a passo fica desligado:
a tarefa é de leitura direta.
"""
from dataclasses import dataclass
from pathlib import Path

MODELO_ID = "Qwen/Qwen3-8B"
MODELO_REVISAO = "b968826d9c46dd6066d109eabc6255188de91218"

# Os pesos são baixados antes da execução, por `baixar_modelo.py`, e ficam no
# cache do repositório. Em bfloat16 o modelo ocupa cerca de 16,4 GB e cabe
# numa só placa de 24 GB, que é o limite das regras de execução.
#
# `device_map="auto"` acomoda tanto a placa única da avaliação quanto as duas
# do Kaggle, onde "balanced" era necessário porque 16,4 GB não cabem numa T4
# de 16 GB. "auto" reparte do mesmo modo quando há duas placas e usa a única
# quando há uma, de modo que o mesmo código serve aos dois ambientes.
DEVICE_MAP_PADRAO = "auto"

# A execução da avaliação não tem internet. Apontar o cache para dentro do
# repositório, e exigir modo offline, faz o carregamento falhar de imediato
# e com mensagem clara se os pesos não tiverem sido baixados antes, em vez de
# tentar alcançar a rede e expirar.
CACHE_DO_MODELO = Path(__file__).resolve().parent.parent / "modelo"


@dataclass
class RespostaLLM:
    texto: str


class QwenClassificador:
    """Mantém o modelo carregado para todas as chamadas do pipeline.

    Os pesos só são baixados e distribuídos na primeira pergunta. A maioria
    dos documentos resolve todas as citações pela estrutura, e carregar
    dezesseis gigabytes para não perguntar nada custa a metade do tempo de
    execução.
    """

    def __init__(self, device_map: str = DEVICE_MAP_PADRAO):
        self._device_map = device_map
        self._tokenizer = None
        self._model = None

    def _carregar(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # O cache local e o modo offline valem para esta carga: os pesos já
        # estão em disco, e alcançar a rede não é permitido nem necessário.
        comuns = {
            "revision": MODELO_REVISAO,
            "cache_dir": str(CACHE_DO_MODELO),
            "local_files_only": True,
        }
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(MODELO_ID, **comuns)
            # As camadas são distribuídas pelas GPUs disponíveis: a placa
            # única da avaliação recebe o modelo inteiro.
            # `torch_dtype`, e não `dtype`: é o nome que `from_pretrained`
            # aceita na versão fixada em requirements.txt, e passar o outro
            # levanta TypeError antes de carregar qualquer peso.
            self._model = AutoModelForCausalLM.from_pretrained(
                MODELO_ID,
                torch_dtype=torch.bfloat16,
                device_map=self._device_map,
                **comuns,
            )
        except OSError as erro:
            raise RuntimeError(
                f"pesos de {MODELO_ID} não encontrados em {CACHE_DO_MODELO}."
                " Rode `python baixar_modelo.py` antes da execução, com"
                " internet disponível."
            ) from erro
        self._model.eval()

    @property
    def tokenizer(self):
        self._carregar()
        return self._tokenizer

    @property
    def model(self):
        self._carregar()
        return self._model

    @property
    def carregado(self) -> bool:
        """O modelo já ocupou memória."""
        return self._model is not None

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

        Sem prompts nada é carregado: a saída vazia precede qualquer toque
        no modelo.
        """
        if not prompts_usuario:
            return []

        import torch

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

    def gerar(
        self, prompt_sistema: str, prompt_usuario: str, max_novos_tokens: int = 512
    ) -> RespostaLLM:
        return self.gerar_lote(prompt_sistema, [prompt_usuario], max_novos_tokens)[0]
