from flask import Blueprint, request, jsonify
from decimal import Decimal
from app import db, csrf
from app.models import (
    VendaPeca,
    EstoquePeca,
    EstoqueMovimentacao
)
from app.services.pagamento.mercadopago_client import MercadoPagoClient
from app.utils_datetime import utc_now

bp_webhook_fitcell = Blueprint("webhook_fitcell", __name__)

@bp_webhook_fitcell.route("/webhook_fitcell/teste", methods=["GET", "POST"])
def teste_wb_fitcell():
    return jsonify({
        "status": "ok",
        "metodo": request.method
    })


@bp_webhook_fitcell.route("/webhook/mercadopago/fitcell", methods=["POST"])
@csrf.exempt
def webhook_mercadopago_fitcell():

    data = request.get_json(silent=True) or {}

    # =================================================
    # FILTRA EVENTOS
    # =================================================
    if data.get("type") != "payment":
        return jsonify({"status": "ignored"}), 200

    pagamento_id = data.get("data", {}).get("id")
    if not pagamento_id:
        return jsonify({"error": "payment id missing"}), 400

    # =================================================
    # BUSCA VENDA (LOCK PARA CONCORRÊNCIA)
    # =================================================
    venda = (
        VendaPeca.query
        .filter_by(pagamento_id=str(pagamento_id))
        .with_for_update()
        .first()
    )

    if not venda:
        return jsonify({"status": "venda not found"}), 200

    # =================================================
    # IDEMPOTÊNCIA
    # =================================================
    if venda.status == "FINALIZADA":
        return jsonify({"status": "already processed"}), 200

    if venda.status == "CANCELADA":
        return jsonify({"status": "venda cancelada"}), 200

    # =================================================
    # CONSULTA MERCADO PAGO
    # =================================================
    mp = MercadoPagoClient(venda.empresa_id)
    pagamento = mp.consultar_pagamento(pagamento_id)

    status_mp = pagamento.get("status")
    valor_pago = Decimal(str(pagamento.get("transaction_amount", 0)))

    # =================================================
    # NÃO APROVADO
    # =================================================
    if status_mp != "approved":
        venda.pagamento_status = status_mp
        db.session.commit()
        return jsonify({"status": "not approved"}), 200

    # =================================================
    # CONFERE VALOR
    # =================================================
    if valor_pago != venda.valor_total:
        return jsonify({"error": "valor divergente"}), 400

    # =================================================
    # CONFIRMA PAGAMENTO
    # =================================================
    venda.pagamento_status = status_mp
    venda.pago_em = utc_now()
    venda.status = "FINALIZADA"

    # =================================================
    # BAIXA ESTOQUE
    # =================================================
    _baixar_estoque_venda(venda)

    db.session.commit()

    return jsonify({"status": "ok"}), 200


### BAIXAR ESTOQUE APÓS O PAGAMENTO PIX ####
from app.models import EstoqueMovimentacao, EstoquePeca
from app import db
from app.utils_datetime import utc_now

def _baixar_estoque_venda(venda):

    for item in venda.itens:

        # MOVIMENTAÇÃO
        db.session.add(
            EstoqueMovimentacao(
                empresa_id=venda.empresa_id,
                peca_id=item.peca_id,
                tipo="saida",
                quantidade=item.quantidade,
                observacao=f"Venda Pix #{venda.id}",
                criado_em=utc_now()
            )
        )

        # ATUALIZA ESTOQUE
        estoque = (
            EstoquePeca.query
            .filter_by(
                empresa_id=venda.empresa_id,
                peca_id=item.peca_id
            )
            .with_for_update()
            .first()
        )

        if not estoque:
            estoque = EstoquePeca(
                empresa_id=venda.empresa_id,
                peca_id=item.peca_id,
                quantidade=0
            )
            db.session.add(estoque)

        estoque.quantidade -= item.quantidade
