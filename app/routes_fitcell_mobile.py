from decimal import Decimal
import os
from flask import current_app, jsonify, make_response, render_template, redirect, url_for, request, flash
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from weasyprint import HTML
from werkzeug.utils import secure_filename  # 🔹 Para salvar o nome do arquivo corretamente

from app import db
from app.models import CompatibilidadePeca, CompraEstoque, CompraEstoqueItem, EstoqueMovimentacao, EstoquePeca, Fornecedor, MarcaCelular, ModeloCelular, Peca, TipoPeca, VendaPeca, VendaPecaItem
from app.forms import CompraEstoqueForm, FornecedorForm, MarcaCelularForm, ModeloCelularForm, PecaForm, TipoPecaForm, VendaPecaForm
from app.services.pagamento.mercadopago_client import MercadoPagoClient
from app.utils import formatar_data, formatar_data_hora, formatar_moeda, requer_permissao

from sqlalchemy.exc import IntegrityError

from app import csrf


from app.routes import bp
from app.utils_datetime import utc_now
from app.utils_licenca import requer_licenca_ativa  # ← IMPORTA O MESMO BLUEPRINT DO routes.py
from app.utils_uploads import salvar_upload


##helpers  de DATAS PARA AS ROTAS ##

from datetime import datetime, time
from app.utils_datetime import br_to_utc

def periodo_datetime(data_ini, data_fim):
    dt_ini = None
    dt_fim = None

    if data_ini:
        dt_ini_br = datetime.combine(
            datetime.strptime(data_ini, "%Y-%m-%d").date(),
            time.min
        )
        dt_ini = br_to_utc(dt_ini_br)

    if data_fim:
        dt_fim_br = datetime.combine(
            datetime.strptime(data_fim, "%Y-%m-%d").date(),
            time.max
        )
        dt_fim = br_to_utc(dt_fim_br)

    return dt_ini, dt_fim


@bp.route('/teste_fitcell_mobile')
@login_required
@requer_permissao("administrativo", "ver")
def teste_fitcell_mobile():
    print('chegou na rota fitcell MOBILE')
    return render_template('fitcell/mobile/teste_fitcell.html')

@bp.route("/fitcell_mobile/marcas")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_marcas_mobile():

    page = request.args.get("page", 1, type=int)
    per_page = 15

    busca = request.args.get("busca", "").strip()

    query = MarcaCelular.query_empresa()

    if busca:
        b = f"%{busca}%"
        query = query.filter(MarcaCelular.nome.ilike(b))

    pagination = (
        query
        .order_by(MarcaCelular.nome)
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "fitcell/mobile/marcas_listar_mobile.html",
        marcas=pagination.items,
        pagination=pagination,
        busca=busca
    )

@bp.route("/fitcell_mobile/marcas/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_nova_marca_mobile():

    form = MarcaCelularForm()

    if form.validate_on_submit():
        marca = MarcaCelular(
            empresa_id=current_user.empresa_id,
            nome=form.nome.data.strip(),
            ativo=form.ativo.data
        )

        db.session.add(marca)

        try:
            db.session.commit()
            flash("Marca cadastrada com sucesso!", "success")
            return redirect(url_for("routes.fitcell_listar_marcas_mobile"))
        except IntegrityError:
            db.session.rollback()
            flash("Esta marca já está cadastrada.", "danger")

    return render_template(
        "fitcell/mobile/marcas_form_mobile.html",
        form=form
    )

@bp.route("/fitcell_mobile/marcas/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_marca_mobile(id):

    marca = (
        MarcaCelular.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    form = MarcaCelularForm(obj=marca)

    if form.validate_on_submit():
        marca.nome = form.nome.data.strip()
        marca.ativo = form.ativo.data

        try:
            db.session.commit()
            flash("Marca atualizada com sucesso!", "success")
            return redirect(url_for("routes.fitcell_listar_marcas_mobile"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao atualizar marca.", "danger")

    return render_template(
        "fitcell/mobile/marcas_form_mobile.html",
        form=form,
        marca=marca
    )

@bp.route("/fitcell_mobile/marcas/<int:id>/excluir", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "excluir")
def fitcell_excluir_marca_mobile(id):

    marca = (
        MarcaCelular.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    modelos_vinculados = (
        ModeloCelular.query_empresa()
        .filter_by(marca_id=marca.id)
        .count()
    )

    if modelos_vinculados > 0:
        flash(
            "Não é possível excluir esta marca pois existem modelos vinculados.",
            "danger"
        )
        return redirect(url_for("routes.fitcell_listar_marcas_mobile"))

    try:
        db.session.delete(marca)
        db.session.commit()
        flash("Marca excluída com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao excluir marca.", "danger")

    return redirect(url_for("routes.fitcell_listar_marcas_mobile"))


@bp.route("/fitcell_mobile/modelos")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_modelos_mobile():

    page = request.args.get("page", 1, type=int)
    per_page = 15

    busca = request.args.get("busca", "").strip()

    query = (
        ModeloCelular.query_empresa()
        .join(MarcaCelular)
    )

    if busca:
        b = f"%{busca}%"
        query = query.filter(
            db.or_(
                ModeloCelular.nome.ilike(b),
                ModeloCelular.variante.ilike(b),
                MarcaCelular.nome.ilike(b)
            )
        )

    pagination = (
        query
        .order_by(MarcaCelular.nome, ModeloCelular.nome)
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "fitcell/mobile/modelos_listar_mobile.html",
        modelos=pagination.items,
        pagination=pagination,
        busca=busca
    )

@bp.route("/fitcell_mobile/modelos/novo", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_novo_modelo_mobile():

    form = ModeloCelularForm()

    form.marca_id.choices = [
        (m.id, m.nome)
        for m in MarcaCelular.query_empresa()
        .filter_by(ativo=True)
        .order_by(MarcaCelular.nome)
        .all()
    ]

    if form.validate_on_submit():
        modelo = ModeloCelular(
            empresa_id=current_user.empresa_id,
            marca_id=form.marca_id.data,
            nome=form.nome.data.strip(),
            variante=form.variante.data.strip() if form.variante.data else None,
            ativo=form.ativo.data
        )

        db.session.add(modelo)

        try:
            db.session.commit()
            flash("Modelo cadastrado com sucesso!", "success")
            return redirect(url_for("routes.fitcell_listar_modelos_mobile"))
        except IntegrityError:
            db.session.rollback()
            flash("Este modelo já está cadastrado para esta marca.", "danger")

    return render_template(
        "fitcell/mobile/modelos_form_mobile.html",
        form=form
    )

@bp.route("/fitcell_mobile/modelos/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_modelo_mobile(id):

    modelo = (
        ModeloCelular.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    form = ModeloCelularForm(obj=modelo)

    form.marca_id.choices = [
        (m.id, m.nome)
        for m in MarcaCelular.query_empresa()
        .filter_by(ativo=True)
        .order_by(MarcaCelular.nome)
        .all()
    ]

    if form.validate_on_submit():
        modelo.marca_id = form.marca_id.data
        modelo.nome = form.nome.data.strip()
        modelo.variante = form.variante.data.strip() if form.variante.data else None
        modelo.ativo = form.ativo.data

        try:
            db.session.commit()
            flash("Modelo atualizado com sucesso!", "success")
            return redirect(url_for("routes.fitcell_listar_modelos_mobile"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao atualizar modelo.", "danger")

    return render_template(
        "fitcell/mobile/modelos_form_mobile.html",
        form=form,
        modelo=modelo
    )

@bp.route("/fitcell_mobile/modelos/<int:id>/excluir", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "excluir")
def fitcell_excluir_modelo_mobile(id):

    modelo = (
        ModeloCelular.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    try:
        db.session.delete(modelo)
        db.session.commit()
        flash("Modelo excluído com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao excluir modelo.", "danger")

    return redirect(url_for("routes.fitcell_listar_modelos_mobile"))


@bp.route("/fitcell_mobile/pecas")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_pecas_mobile():

    page = request.args.get("page", 1, type=int)
    busca = request.args.get("busca", "").strip()

    query = (
        db.session.query(
            Peca,
            EstoquePeca.quantidade
        )
        .outerjoin(
            EstoquePeca,
            EstoquePeca.peca_id == Peca.id
        )
        .filter(Peca.empresa_id == current_user.empresa_id)
    )

    if busca:
        query = query.filter(
            or_(
                Peca.codigo_interno.ilike(f"%{busca}%"),
                Peca.nome.ilike(f"%{busca}%"),
                Peca.marca_peca.ilike(f"%{busca}%"),
                Peca.qualidade.ilike(f"%{busca}%"),
                Peca.tipo.has(TipoPeca.nome.ilike(f"%{busca}%"))
            )
        )

    pecas = query.order_by(Peca.id.desc()).paginate(page=page, per_page=20)

    return render_template(
        "fitcell/mobile/pecas_listar_mobile.html",
        pecas=pecas,
        busca=busca
    )

@bp.route("/fitcell_mobile/pecas/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_nova_peca_mobile():

    form = PecaForm()
    form.carregar_choices(current_user.empresa_id)

    if form.validate_on_submit():

        peca = Peca(
            empresa_id=current_user.empresa_id,
            nome=form.nome.data,
            tipo_peca_id=form.tipo_peca_id.data,
            qualidade=form.qualidade.data,
            preco_venda=form.preco_venda.data,
            preco_minimo=form.preco_minimo.data,
            codigo_interno=form.codigo_interno.data,
            marca_peca=form.marca_peca.data,
            observacoes=form.observacoes.data,
            ativo=True
        )

        if form.imagem.data:
            peca.imagem = salvar_upload(form.imagem.data, subpasta="pecas")

        db.session.add(peca)
        db.session.commit()

        flash("Peça cadastrada com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_pecas_mobile"))

    return render_template(
        "fitcell/mobile/peca_form_mobile.html",
        form=form
    )


@bp.route("/fitcell_mobile/pecas/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_peca_mobile(id):

    peca = (
        Peca.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    form = PecaForm(obj=peca)
    form.carregar_choices(current_user.empresa_id)

    if request.method == "GET":
        form.modelos_compativeis.data = [
            c.modelo_celular_id
            for c in CompatibilidadePeca.query
                .filter_by(peca_id=peca.id)
                .all()
        ]

    if form.validate_on_submit():

        peca.nome = form.nome.data
        peca.tipo_peca_id = form.tipo_peca_id.data
        peca.qualidade = form.qualidade.data
        peca.preco_venda = form.preco_venda.data
        peca.preco_minimo = form.preco_minimo.data
        peca.codigo_interno = form.codigo_interno.data
        peca.marca_peca = form.marca_peca.data
        peca.observacoes = form.observacoes.data
        peca.ativo = form.ativo.data

        selecionados = set(form.modelos_compativeis.data or [])

        existentes = {
            c.modelo_celular_id: c
            for c in CompatibilidadePeca.query
                .filter_by(peca_id=peca.id)
                .all()
        }

        for modelo_id, compat in existentes.items():
            if modelo_id not in selecionados:
                db.session.delete(compat)

        for modelo_id in selecionados:
            if modelo_id not in existentes:
                db.session.add(
                    CompatibilidadePeca(
                        peca_id=peca.id,
                        modelo_celular_id=modelo_id
                    )
                )

        if form.imagem.data:
            peca.imagem = salvar_upload(form.imagem.data, subpasta="pecas")

        db.session.commit()

        flash("Peça atualizada com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_pecas_mobile"))

    return render_template(
        "fitcell/mobile/peca_form_mobile.html",
        form=form,
        peca=peca
    )

@bp.route("/fitcell_mobile/pecas/<int:id>/excluir", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "excluir")
def fitcell_excluir_peca_mobile(id):

    peca = Peca.query_empresa().filter_by(id=id).first_or_404()

    venda = VendaPecaItem.query.filter_by(peca_id=id).first()
    if venda:
        flash(f"Não é possível excluir. Peça usada na venda #{venda.venda_id}.", "danger")
        return redirect(url_for("routes.fitcell_listar_pecas_mobile"))

    compra = CompraEstoqueItem.query.filter_by(peca_id=id).first()
    if compra:
        flash(f"Não é possível excluir. Peça usada na compra #{compra.compra_id}.", "danger")
        return redirect(url_for("routes.fitcell_listar_pecas_mobile"))

    try:
        db.session.delete(peca)
        db.session.commit()
        flash("Peça excluída com sucesso!", "success")
    except:
        db.session.rollback()
        flash("Erro ao excluir peça.", "danger")

    return redirect(url_for("routes.fitcell_listar_pecas_mobile"))




@bp.route("/fitcell_mobile/fornecedores")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_fornecedores_mobile():

    page = request.args.get("page", 1, type=int)
    per_page = 15
    busca = request.args.get("busca", "").strip()

    query = Fornecedor.query_empresa()

    if busca:
        b = f"%{busca}%"
        query = query.filter(
            db.or_(
                Fornecedor.nome.ilike(b),
                Fornecedor.documento.ilike(b)
            )
        )

    pagination = (
        query
        .order_by(Fornecedor.nome)
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "fitcell/mobile/fornecedores_listar_mobile.html",
        fornecedores=pagination.items,
        pagination=pagination,
        busca=busca
    )


@bp.route("/fitcell_mobile/fornecedores/novo", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_novo_fornecedor_mobile():

    form = FornecedorForm()

    if form.validate_on_submit():

        fornecedor = Fornecedor(
            empresa_id=current_user.empresa_id,
            nome=form.nome.data,
            tipo=form.tipo.data,
            documento=form.documento.data,
            telefone=form.telefone.data,
            email=form.email.data,
            observacoes=form.observacoes.data,
            ativo=form.ativo.data
        )

        db.session.add(fornecedor)
        db.session.commit()

        flash("Fornecedor cadastrado com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_fornecedores_mobile"))

    return render_template(
        "fitcell/mobile/fornecedores_form_mobile.html",
        form=form
    )

@bp.route("/fitcell_mobile/fornecedores/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_fornecedor_mobile(id):

    fornecedor = (
        Fornecedor.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    form = FornecedorForm(obj=fornecedor)

    if form.validate_on_submit():

        fornecedor.nome = form.nome.data
        fornecedor.tipo = form.tipo.data
        fornecedor.documento = form.documento.data
        fornecedor.telefone = form.telefone.data
        fornecedor.email = form.email.data
        fornecedor.observacoes = form.observacoes.data
        fornecedor.ativo = form.ativo.data

        db.session.commit()

        flash("Fornecedor atualizado com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_fornecedores_mobile"))

    return render_template(
        "fitcell/mobile/fornecedores_form_mobile.html",
        form=form,
        fornecedor=fornecedor
    )

@bp.route("/fitcell_mobile/fornecedores/<int:id>/excluir", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("fitcell", "excluir")
def fitcell_excluir_fornecedor_mobile(id):

    fornecedor = Fornecedor.query_empresa().filter_by(id=id).first_or_404()

    compra = CompraEstoque.query.filter_by(fornecedor_id=id).first()
    if compra:
        flash(f"Não é possível excluir. Fornecedor usado na compra #{compra.id}.", "danger")
        return redirect(url_for("routes.fitcell_listar_fornecedores_mobile"))

    try:
        db.session.delete(fornecedor)
        db.session.commit()
        flash("Fornecedor excluído com sucesso!", "success")
    except:
        db.session.rollback()
        flash("Erro ao excluir fornecedor.", "danger")

    return redirect(url_for("routes.fitcell_listar_fornecedores_mobile"))



### COMPRAS  ##
@bp.route("/fitcell_mobile/compras/estoque")
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "ver")
def fitcell_listar_compras_estoque_mobile():

    page = request.args.get("page", 1, type=int)
    per_page = 15

    fornecedor_id = request.args.get("fornecedor_id")
    status = request.args.get("status")
    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    query = (
        CompraEstoque.query_empresa()
        .join(Fornecedor)
    )

    if fornecedor_id:
        query = query.filter(CompraEstoque.fornecedor_id == fornecedor_id)

    if status:
        query = query.filter(CompraEstoque.status == status)

    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    if dt_ini:
        query = query.filter(CompraEstoque.criado_em >= dt_ini)
    if dt_fim:
        query = query.filter(CompraEstoque.criado_em <= dt_fim)

    compras = (
        query
        .order_by(CompraEstoque.criado_em.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    fornecedores = (
        Fornecedor.query_empresa()
        .filter_by(ativo=True)
        .order_by(Fornecedor.nome)
        .all()
    )

    return render_template(
        "fitcell/mobile/compras_estoque_listar_mobile.html",
        compras=compras,
        fornecedores=fornecedores,
        fornecedor_id=fornecedor_id,
        status=status,
        data_ini=data_ini,
        data_fim=data_fim
    )

@bp.route("/fitcell_mobile/compras/estoque/<int:id>")
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "ver")
def fitcell_ver_compra_estoque_mobile(id):

    compra = (
        CompraEstoque.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    itens = (
        CompraEstoqueItem.query
        .filter_by(compra_id=compra.id)
        .join(Peca)
        .order_by(Peca.id)
        .all()
    )

    total_compra = sum(
        (i.quantidade or 0) * (i.custo_unitario or 0)
        for i in itens
    )

    return render_template(
        "fitcell/mobile/compra_estoque_detalhe_mobile.html",
        compra=compra,
        itens=itens,
        total_compra=total_compra
    )


@bp.route("/fitcell_mobile/compras/estoque/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "criar")
def fitcell_nova_compra_estoque_mobile():

    form = CompraEstoqueForm()

    form.fornecedor_id.choices = [
        (f.id, f.nome)
        for f in (
            Fornecedor.query_empresa()
            .filter_by(ativo=True)
            .order_by(Fornecedor.nome)
            .all()
        )
    ]

    pecas = (
        Peca.query_empresa()
        .filter_by(ativo=True)
        .order_by(Peca.id.desc())
        .all()
    )

    if request.method == "POST" and form.validate():

        pecas_ids = request.form.getlist("peca_id[]")
        quantidades = request.form.getlist("quantidade[]")
        custos = request.form.getlist("custo_unitario[]")

        if not pecas_ids:
            flash("Adicione pelo menos uma peça.", "danger")
            return redirect(request.url)

        compra = CompraEstoque(
            empresa_id=current_user.empresa_id,
            fornecedor_id=form.fornecedor_id.data,
            observacao=form.observacao.data,
            criado_em=utc_now()
        )

        db.session.add(compra)
        db.session.flush()

        for peca_id, qtd, custo in zip(pecas_ids, quantidades, custos):

            peca_id = int(peca_id)
            quantidade = int(qtd)
            custo = float(custo)

            if quantidade <= 0:
                continue

            db.session.add(
                CompraEstoqueItem(
                    compra_id=compra.id,
                    peca_id=peca_id,
                    quantidade=quantidade,
                    custo_unitario=custo
                )
            )

            db.session.add(
                EstoqueMovimentacao(
                    empresa_id=current_user.empresa_id,
                    peca_id=peca_id,
                    fornecedor_id=compra.fornecedor_id,
                    compra_id=compra.id,
                    tipo="entrada",
                    quantidade=quantidade,
                    observacao=f"Compra #{compra.id}",
                    criado_em=utc_now()
                )
            )

            estoque = EstoquePeca.query_empresa().filter_by(peca_id=peca_id).first()

            if not estoque:
                estoque = EstoquePeca(
                    empresa_id=current_user.empresa_id,
                    peca_id=peca_id,
                    quantidade=0
                )
                db.session.add(estoque)

            estoque.quantidade += quantidade

        db.session.commit()

        flash("Compra registrada com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_compras_estoque_mobile"))

    return render_template(
        "fitcell/mobile/compras_estoque_form_mobile.html",
        form=form,
        pecas=pecas
    )

@bp.route("/fitcell_mobile/compras/estoque/<int:compra_id>/estornar", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "editar")
def fitcell_estornar_compra_estoque_mobile(compra_id):

    compra = (
        CompraEstoque.query_empresa()
        .filter_by(id=compra_id)
        .first_or_404()
    )

    if compra.status == "ESTORNADA":
        flash("Esta compra já foi estornada.", "warning")
        return redirect(url_for("routes.fitcell_listar_compras_estoque_mobile"))

    movimentacoes = (
        EstoqueMovimentacao.query_empresa()
        .filter_by(
            compra_id=compra.id,
            tipo="entrada"
        )
        .all()
    )

    if not movimentacoes:
        flash("Nenhuma movimentação encontrada para estorno.", "danger")
        return redirect(url_for("routes.fitcell_listar_compras_estoque_mobile"))

    for mov in movimentacoes:

        estoque = (
            EstoquePeca.query_empresa()
            .filter_by(peca_id=mov.peca_id)
            .first()
        )

        qtd_estoque = estoque.quantidade if estoque else 0

        if qtd_estoque < mov.quantidade:
            flash(
                f"Não é possível estornar. "
                f"A peça {mov.peca.nome} já possui vendas associadas.",
                "danger"
            )
            return redirect(url_for("routes.fitcell_listar_compras_estoque_mobile"))

    for mov in movimentacoes:

        db.session.add(
            EstoqueMovimentacao(
                empresa_id=compra.empresa_id,
                peca_id=mov.peca_id,
                fornecedor_id=mov.fornecedor_id,
                compra_id=compra.id,
                tipo="estorno",
                quantidade=-mov.quantidade,
                movimentacao_origem_id=mov.id,
                observacao=f"Estorno da compra #{compra.id}",
                criado_em=utc_now()
            )
        )

        estoque = (
            EstoquePeca.query_empresa()
            .filter_by(peca_id=mov.peca_id)
            .first()
        )

        if estoque:
            estoque.quantidade -= mov.quantidade

    compra.status = "ESTORNADA"
    compra.estornada_em = utc_now()

    db.session.commit()

    flash("Compra estornada com sucesso!", "success")
    return redirect(url_for("routes.fitcell_listar_compras_estoque_mobile"))


@bp.route("/fitcell_mobile/estoque/movimentacoes")
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "ver")
def fitcell_listar_movimentacoes_estoque_mobile():

    page = request.args.get("page", 1, type=int)
    per_page = 20
    busca = request.args.get("busca", "").strip()
    tipo = request.args.get("tipo")

    query = (
        EstoqueMovimentacao.query_empresa()
        .join(Peca)
        .outerjoin(Fornecedor)
    )

    if tipo:
        query = query.filter(EstoqueMovimentacao.tipo == tipo)

    if busca:
        b = f"%{busca}%"
        query = query.filter(
            db.or_(
                Peca.codigo_interno.ilike(b),
                Peca.marca_peca.ilike(b),
                EstoqueMovimentacao.observacao.ilike(b)
            )
        )

    pagination = (
        query
        .order_by(EstoqueMovimentacao.criado_em.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "fitcell/mobile/estoque_movimentacoes_listar_mobile.html",
        movimentacoes=pagination.items,
        pagination=pagination,
        busca=busca,
        tipo=tipo
    )




@bp.route("/fitcell_mobile/vendas/pecas", endpoint="fitcell_listar_vendas_pecas_mobile")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_listar_vendas_pecas_mobile():

    page = request.args.get("page", 1, type=int)
    busca = request.args.get("busca", "")
    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    query = (
        db.session.query(
            VendaPeca,
            func.coalesce(func.sum(VendaPecaItem.quantidade), 0).label("qtd_itens")
        )
        .outerjoin(VendaPecaItem, VendaPecaItem.venda_id == VendaPeca.id)
        .filter(VendaPeca.empresa_id == current_user.empresa_id,
                VendaPeca.status != "ORCAMENTO"   # 👈 ESSENCIAL
                )
        
        .group_by(VendaPeca.id)
        .order_by(VendaPeca.criado_em.desc())
    )


    # =========================
    # BUSCA
    # =========================
    if busca:
        query = query.filter(
            db.or_(
                VendaPeca.cliente_nome.ilike(f"%{busca}%"),
                VendaPeca.cliente_telefone.ilike(f"%{busca}%")
            )
        )

    # =========================
    # FILTRO DE DATAS (OPCIONAL)
    # =========================
    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    if dt_ini:
        query = query.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        query = query.filter(VendaPeca.criado_em <= dt_fim)

    pagination = query.paginate(page=page, per_page=20)

    return render_template(
        "fitcell/mobile/vendas_peca_listar_mobile.html",
        vendas=pagination.items,
        pagination=pagination,
        busca=busca,
        data_ini=data_ini,
        data_fim=data_fim
    )


@bp.route("/fitcell_mobile/vendas/pecas/receber-pix", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "criar")
def fitcell_receber_via_pix_mobile():

    form = VendaPecaForm()

    # ========= MODELO =========
    form.modelo_celular_id.choices = [
        (m.id, f"{m.marca.nome} {m.nome}".strip())
        for m in ModeloCelular.query_empresa()
        .filter_by(ativo=True)
        .order_by(ModeloCelular.nome)
        .all()
    ]

    if not form.validate():
        flash("Dados inválidos na venda.", "danger")
        return redirect(request.referrer)

    pecas_ids = request.form.getlist("peca_id[]")
    quantidades = request.form.getlist("quantidade[]")
    valores = request.form.getlist("valor_unitario[]")

    if not pecas_ids:
        flash("Adicione pelo menos uma peça.", "danger")
        return redirect(request.referrer)

    # ========= CRIA VENDA (SEM BAIXAR ESTOQUE) =========
    venda = VendaPeca(
        empresa_id=current_user.empresa_id,
        modelo_celular_id=form.modelo_celular_id.data,
        cliente_nome=form.cliente_nome.data,
        cliente_telefone=form.cliente_telefone.data,
        tipo_pagamento="pix",
        desconto=form.desconto.data or 0,
        status="AGUARDANDO_PAGAMENTO",
        origem="manual",
        criado_em=utc_now()
    )

    db.session.add(venda)
    db.session.flush()

    total_venda = 0

    for peca_id, qtd, valor in zip(pecas_ids, quantidades, valores):

        quantidade = int(qtd)
        valor_unitario = Decimal(valor)

        if quantidade <= 0:
            continue

        valor_total_item = quantidade * valor_unitario
        total_venda += valor_total_item

        db.session.add(
            VendaPecaItem(
                venda_id=venda.id,
                peca_id=int(peca_id),
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                valor_total=valor_total_item
            )
        )

    total_venda -= Decimal(venda.desconto or 0)
    venda.valor_total = total_venda

    # ========= MERCADO PAGO =========
    mp = MercadoPagoClient(current_user.empresa_id)

    telefone = venda.cliente_telefone or venda.id
    telefone = ''.join(filter(str.isdigit, str(telefone)))

    email_cliente = f"cliente{telefone}@fitcell.com.br"



    pagamento = mp.criar_pagamento(
        valor=venda.valor_total,
        descricao=f"Venda FITCELL #{venda.id}",
        email=email_cliente
    )

    venda.pagamento_id = str(pagamento["id"])
    venda.pagamento_status = pagamento["status"]

    poi = pagamento.get("point_of_interaction", {})
    tx = poi.get("transaction_data")

    if not tx:
        current_app.logger.error(f"PIX não gerado: {pagamento}")

        flash(
            "Não foi possível gerar o QR Code Pix. Verifique os dados e tente novamente.",
            "danger"
        )
        db.session.rollback()
        return redirect(request.referrer)

    venda.pix_qr_code = tx.get("qr_code")
    venda.pix_qr_code_base64 = tx.get("qr_code_base64")


    db.session.commit()

    return redirect(
        url_for("routes.fitcell_ver_venda_peca_mobile", id=venda.id)
    )

@bp.route("/fitcell_mobile/vendas/pecas/<int:id>", endpoint="fitcell_ver_venda_peca_mobile")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_ver_venda_peca_mobile(id):

    venda = (
        VendaPeca.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    return render_template(
        "fitcell/mobile/vendas_peca_detalhe_mobile.html",
        venda=venda
    )

@bp.route("/fitcell_mobile/vendas/pecas/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "criar")
def fitcell_nova_venda_peca_mobile():

    form = VendaPecaForm()

    # ==========================
    # MODELOS DE CELULAR
    # ==========================
    form.modelo_celular_id.choices = [
        (m.id, f"{m.marca.nome} {m.nome} {m.variante}".strip())
        for m in (
            ModeloCelular.query_empresa()
            .filter_by(ativo=True)
            .order_by(ModeloCelular.nome)
            .all()
        )
    ]

    pecas = []

    # ==========================
    # FILTRA PEÇAS PELO MODELO
    # ==========================
    modelo_id = request.args.get("modelo_id", type=int)

    if modelo_id:
        form.modelo_celular_id.data = modelo_id

        pecas = (
            Peca.query_empresa()
            .join(CompatibilidadePeca)
            .filter(
                CompatibilidadePeca.modelo_celular_id == modelo_id,
                Peca.ativo == True
            )
            .order_by(Peca.id.desc())
            .all()
        )

    # ==========================
    # SUBMIT DA VENDA
    # ==========================
    if request.method == "POST" and form.validate():

        pecas_ids = request.form.getlist("peca_id[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor_unitario[]")

        if not pecas_ids:
            flash("Adicione pelo menos uma peça na venda.", "danger")
            return redirect(request.url)

        venda = VendaPeca(
            empresa_id=current_user.empresa_id,
            modelo_celular_id=form.modelo_celular_id.data,
            cliente_nome=form.cliente_nome.data,
            cliente_telefone=form.cliente_telefone.data,
            tipo_pagamento=form.tipo_pagamento.data,
            desconto=form.desconto.data or 0,
            status="FINALIZADA",
            origem="manual",
            criado_em=utc_now(),
            pago_em=utc_now()
        )

        db.session.add(venda)
        db.session.flush()  # gera venda.id

        total_venda = 0

        for peca_id, qtd, valor in zip(pecas_ids, quantidades, valores):

            peca_id = int(peca_id)
            quantidade = int(qtd)
            valor_unitario = float(valor)

            if quantidade <= 0:
                continue

            valor_total_item = quantidade * valor_unitario
            total_venda += valor_total_item

            # ITEM DA VENDA
            db.session.add(
                VendaPecaItem(
                    venda_id=venda.id,
                    peca_id=peca_id,
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_total_item
                )
            )

            # MOVIMENTAÇÃO DE ESTOQUE (SAÍDA)
            db.session.add(
                EstoqueMovimentacao(
                    empresa_id=current_user.empresa_id,
                    peca_id=peca_id,
                    tipo="saida",
                    quantidade=quantidade,
                    observacao=f"Venda #{venda.id}",
                    criado_em=utc_now()
                )
            )

            # ATUALIZA ESTOQUE
            estoque = (
                EstoquePeca.query_empresa()
                .filter_by(peca_id=peca_id)
                .first()
            )

            if not estoque:
                estoque = EstoquePeca(
                    empresa_id=current_user.empresa_id,
                    peca_id=peca_id,
                    quantidade=0
                )
                db.session.add(estoque)

            estoque.quantidade -= quantidade

        # DESCONTO GERAL
        total_venda -= float(venda.desconto or 0)
        venda.valor_total = total_venda

        db.session.commit()

        flash("Venda registrada com sucesso!", "success")
        return redirect(
            url_for("routes.fitcell_ver_venda_peca_mobile", id=venda.id)
        )


    return render_template(
        "fitcell/mobile/vendas_peca_form_mobile.html",
        form=form,
        pecas=pecas
    )
