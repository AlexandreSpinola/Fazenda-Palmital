"""
Envia um lote gerado pelo gerar_lote_cvat.py para o CVAT local:
cria (se preciso) o projeto com o rotulo 'vaca', cria a task com as imagens,
importa as pre-anotacoes e divide em jobs (opcionalmente ja atribuidos).

Credenciais: variaveis de ambiente CVAT_USUARIO e CVAT_SENHA; se nao
existirem, o script pergunta (a senha nao aparece na tela).

Uso:
    python enviar_lote_cvat.py lotes\\lote_001
    python enviar_lote_cvat.py lotes\\lote_001 --frames-por-job 50 --responsaveis aluno1,aluno2
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

from cvat_sdk import make_client
from cvat_sdk.core.proxies.tasks import ResourceType

HOST_PADRAO = "http://100.84.211.55:8080"
PROJETO_PADRAO = "Vacas no cocho"
ROTULO = "vaca"
FORMATO_ANOTACOES = "CVAT 1.1"


def obter_projeto(client, nome):
    for p in client.projects.list():
        if p.name == nome:
            return p
    print(f"Criando o projeto '{nome}' (rotulo '{ROTULO}', poligono)...")
    return client.projects.create(spec={
        "name": nome,
        "labels": [{"name": ROTULO, "type": "polygon", "color": "#ff3030"}],
    })


def buscar_usuarios(client, nomes):
    por_nome = {u.username: u for u in client.users.list()}
    faltando = [n for n in nomes if n not in por_nome]
    if faltando:
        sys.exit("Usuario(s) nao encontrado(s) no CVAT: " + ", ".join(faltando)
                 + "\n(o estudante precisa ter criado a conta antes)")
    return [por_nome[n] for n in nomes]


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("lote", help="pasta do lote (contem imagens/ e anotacoes_cvat.zip)")
    p.add_argument("--nome", help="nome da task (padrao: nome da pasta do lote)")
    p.add_argument("--projeto", default=PROJETO_PADRAO)
    p.add_argument("--frames-por-job", type=int, default=50,
                   help="imagens por job; cada job e uma unidade de trabalho de um estudante (padrao 50)")
    p.add_argument("--responsaveis", default="",
                   help="usuarios do CVAT separados por virgula; os jobs sao distribuidos em rodizio")
    p.add_argument("--host", default=os.environ.get("CVAT_HOST_URL", HOST_PADRAO))
    args = p.parse_args()

    lote = Path(args.lote)
    imagens = sorted((lote / "imagens").glob("*.jpg"))
    anotacoes = lote / "anotacoes_cvat.zip"
    if not imagens:
        sys.exit(f"Nenhuma imagem em {lote / 'imagens'}")
    if not anotacoes.exists():
        sys.exit(f"Arquivo de pre-anotacoes nao encontrado: {anotacoes}")

    usuario = os.environ.get("CVAT_USUARIO") or input("Usuario do CVAT: ")
    senha = os.environ.get("CVAT_SENHA") or getpass.getpass("Senha do CVAT: ")
    responsaveis = [n.strip() for n in args.responsaveis.split(",") if n.strip()]

    with make_client(args.host, credentials=(usuario, senha)) as client:
        projeto = obter_projeto(client, args.projeto)
        pessoas = buscar_usuarios(client, responsaveis) if responsaveis else []

        nome = args.nome or lote.name
        print(f"Enviando {len(imagens)} imagens para a task '{nome}'...")
        task = client.tasks.create_from_data(
            spec={"name": nome, "project_id": projeto.id, "segment_size": args.frames_por_job},
            resources=[str(i) for i in imagens],
            resource_type=ResourceType.LOCAL,
            # ordem alfabetica: e a ordem assumida pelos ids do XML de pre-anotacoes
            data_params={"image_quality": 95, "sorting_method": "lexicographical"},
        )

        print("Importando as pre-anotacoes...")
        task.import_annotations(FORMATO_ANOTACOES, str(anotacoes))

        jobs = sorted(task.get_jobs(), key=lambda j: j.start_frame)
        for i, job in enumerate(jobs):
            if pessoas:
                job.update({"assignee": pessoas[i % len(pessoas)].id})
        print(f"\nTask criada: {args.host}/tasks/{task.id}")
        for job in jobs:
            dono = next((u.username for u in pessoas if u.id == getattr(job.assignee, "id", None)), "-")
            print(f"  job {job.id}: frames {job.start_frame}-{job.stop_frame}  responsavel: {dono}")


if __name__ == "__main__":
    main()
