#!/bin/sh
# Envia ao GitHub as bases que a Biblioteca indexou no servidor.
#
# Quando uma indexação termina com documentos novos, o SensorChat grava
# /dados/indexado.json no volume. Este script fica de olho nesse aviso: copia as bases do
# volume para o repositório, faz commit e push. Roda como serviço
# (scripts/sensorchat-sincronizar.service) a partir da pasta do projeto no servidor.

cd "$(dirname "$0")/.." || exit 1

DADOS="base_*.json base_*.npz catalogo.json extracoes.json grafo.json grafo.npz"
AVISO=/dados/indexado.json
EM_ENVIO=/dados/indexado.enviando.json
INTERVALO=${INTERVALO:-30}

no_container() {
    docker compose exec -T sensorchat sh -c "$1"
}

sincronizar() {
    pacote=$(mktemp) || return 1
    no_container "cd /dados && tar -c $DADOS" > "$pacote" && tar -xf "$pacote"
    copiou=$?
    rm -f "$pacote"
    [ $copiou -eq 0 ] || return 1

    git add $DADOS || return 1
    if ! git diff --cached --quiet; then
        git commit -q -m "Atualiza bases indexadas pela Biblioteca" -m "$(no_container "cat $EM_ENVIO")" || return 1
    fi
    git pull -q --rebase || { git rebase --abort; return 1; }
    git push -q
}

while true; do
    if no_container "test -f $AVISO" 2>/dev/null; then
        # Renomeia antes de copiar: se outra indexação terminar durante o envio, o aviso novo
        # fica para a próxima volta.
        no_container "mv $AVISO $EM_ENVIO"
        if sincronizar; then
            no_container "rm -f $EM_ENVIO"
            echo "bases enviadas ao GitHub"
        else
            no_container "[ -f $AVISO ] || mv $EM_ENVIO $AVISO"
            echo "o envio falhou; tento de novo em 10 minutos" >&2
            sleep 600
        fi
    fi
    sleep "$INTERVALO"
done
