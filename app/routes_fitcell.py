from decimal import Decimal
import os
from flask import current_app, jsonify, make_response, render_template, redirect, url_for, request, flash
from flask_login import current_user, login_required
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


@bp.route('/teste_fitcell')
@login_required
@requer_permissao("administrativo", "ver")
def teste_fitcell():
    print('chegou na rota fitcell')
    return render_template('fitcell/teste_fitcell.html')


@bp.route("/fitcell/marcas")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_marcas():

    page = request.args.get("page", 1, type=int)
    per_page = 15

    busca = request.args.get("busca", "").strip()

    query = MarcaCelular.query_empresa()

    if busca:
        b = f"%{busca}%"
        query = query.filter(
            MarcaCelular.nome.ilike(b)
        )

    pagination = (
        query
        .order_by(MarcaCelular.nome)
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "fitcell/marcas_listar.html",
        marcas=pagination.items,
        pagination=pagination,
        busca=busca
    )

@bp.route("/fitcell/marcas/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_nova_marca():

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
            return redirect(url_for("routes.fitcell_listar_marcas"))
        except IntegrityError:
            db.session.rollback()
            flash("Esta marca já está cadastrada.", "danger")

    return render_template(
        "fitcell/marcas_form.html",
        form=form
    )

@bp.route("/fitcell/marcas/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_marca(id):

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
            return redirect(url_for("routes.fitcell_listar_marcas"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao atualizar marca.", "danger")

    return render_template(
        "fitcell/marcas_form.html",
        form=form,
        marca=marca
    )

@bp.route("/fitcell/marcas/<int:id>/excluir", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "excluir")
def fitcell_excluir_marca(id):

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
        return redirect(url_for("routes.fitcell_listar_marcas"))

    try:
        db.session.delete(marca)
        db.session.commit()
        flash("Marca excluída com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao excluir marca.", "danger")

    return redirect(url_for("routes.fitcell_listar_marcas"))


@bp.route("/fitcell/modelos")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_modelos():

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
        "fitcell/modelos_listar.html",
        modelos=pagination.items,
        pagination=pagination,
        busca=busca
    )


@bp.route("/fitcell/modelos/novo", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_novo_modelo():

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
            return redirect(url_for("routes.fitcell_listar_modelos"))
        except IntegrityError:
            db.session.rollback()
            flash("Este modelo já está cadastrado para esta marca.", "danger")

    return render_template(
        "fitcell/modelos_form.html",
        form=form
    )

@bp.route("/fitcell/modelos/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_modelo(id):

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
            return redirect(url_for("routes.fitcell_listar_modelos"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao atualizar modelo.", "danger")

    return render_template(
        "fitcell/modelos_form.html",
        form=form,
        modelo=modelo
    )


@bp.route("/fitcell/modelos/<int:id>/excluir", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("fitcell", "excluir")
def fitcell_excluir_modelo(id):

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

    return redirect(url_for("routes.fitcell_listar_modelos"))


## PEÇA  ###

@bp.route("/fitcell/tipos-peca")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_tipos_peca():

    page = request.args.get("page", 1, type=int)
    busca = request.args.get("busca", "").strip()

    query = TipoPeca.query

    if busca:
        query = query.filter(TipoPeca.nome.ilike(f"%{busca}%"))

    pagination = (
        query
        .order_by(TipoPeca.nome)
        .paginate(page=page, per_page=15, error_out=False)
    )

    return render_template(
        "fitcell/tipo_peca_listar.html",
        tipos=pagination.items,
        pagination=pagination,
        busca=busca
    )

@bp.route("/fitcell/tipos-peca/novo", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_novo_tipo_peca():

    form = TipoPecaForm()

    if form.validate_on_submit():

        tipo = TipoPeca(
            nome=form.nome.data
        )

        db.session.add(tipo)
        db.session.commit()

        flash("Tipo de peça cadastrado com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_tipos_peca"))

    return render_template(
        "fitcell/tipo_peca_form.html",
        form=form,
        titulo="Novo Tipo de Peça"
    )

@bp.route("/fitcell/tipos-peca/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_tipo_peca(id):

    tipo = TipoPeca.query.get_or_404(id)
    form = TipoPecaForm(obj=tipo)

    if form.validate_on_submit():

        tipo.nome = form.nome.data
        db.session.commit()

        flash("Tipo de peça atualizado com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_tipos_peca"))

    return render_template(
        "fitcell/tipo_peca_form.html",
        form=form,
        titulo="Editar Tipo de Peça"
    )

from sqlalchemy import func, or_

@bp.route("/fitcell/pecas")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_pecas():

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

    query = query.order_by(Peca.id.desc())

    pecas = query.paginate(page=page, per_page=20)

    return render_template(
        "fitcell/pecas_listar.html",
        pecas=pecas,
        busca=busca
    )



@bp.route("/fitcell/pecas/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_nova_peca():

    form = PecaForm()

    form.tipo_peca_id.choices = [
        (t.id, t.nome)
        for t in TipoPeca.query.order_by(TipoPeca.nome).all()
    ]

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

        # Salvar imagem se houver
        if form.imagem.data:
            caminho_relativo = salvar_upload(
                form.imagem.data,
                subpasta="pecas"
            )
            peca.imagem = caminho_relativo


        db.session.add(peca)
        db.session.commit()

        flash("Peça cadastrada com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_pecas"))

    return render_template(
        "fitcell/peca_form.html",
        form=form,
        titulo="Nova Peça"
    )

@bp.route("/fitcell/pecas/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_peca(id):

    peca = (
        Peca.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    form = PecaForm(obj=peca)
    form.carregar_choices(current_user.empresa_id)

    # --------------------------------------------------
    # GET → carrega compatibilidades existentes
    # --------------------------------------------------
    if request.method == "GET":
        form.modelos_compativeis.data = [
            c.modelo_celular_id
            for c in CompatibilidadePeca.query
                .filter_by(peca_id=peca.id)
                .all()
        ]

    # --------------------------------------------------
    # POST
    # --------------------------------------------------
    if form.validate_on_submit():

        # 🔹 dados básicos
        peca.nome = form.nome.data
        peca.tipo_peca_id = form.tipo_peca_id.data
        peca.qualidade = form.qualidade.data
        peca.preco_venda = form.preco_venda.data
        peca.preco_minimo = form.preco_minimo.data
        peca.codigo_interno = form.codigo_interno.data
        peca.marca_peca = form.marca_peca.data
        peca.observacoes = form.observacoes.data
        peca.ativo = form.ativo.data



        # --------------------------------------------------
        # 🔥 COMPATIBILIDADE
        # --------------------------------------------------
        selecionados = set(form.modelos_compativeis.data or [])

        existentes = {
            c.modelo_celular_id: c
            for c in CompatibilidadePeca.query
                .filter_by(peca_id=peca.id)
                .all()
        }

        # ➖ remover os desmarcados
        for modelo_id, compat in existentes.items():
            if modelo_id not in selecionados:
                db.session.delete(compat)

        # ➕ adicionar novos
        for modelo_id in selecionados:
            if modelo_id not in existentes:
                db.session.add(
                    CompatibilidadePeca(
                        peca_id=peca.id,
                        modelo_celular_id=modelo_id
                    )
                )

        # Salvar imagem se houver
        if form.imagem.data:
            caminho_relativo = salvar_upload(
                form.imagem.data,
                subpasta="pecas"
            )
            peca.imagem = caminho_relativo

        db.session.commit()

        flash("Peça atualizada com sucesso!", "success")
        return redirect(url_for("routes.fitcell_listar_pecas"))

    return render_template(
        "fitcell/peca_form.html",
        form=form,
        peca=peca
    )


@bp.route("/fitcell/fornecedores")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_listar_fornecedores():

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
        "fitcell/fornecedores_listar.html",
        fornecedores=pagination.items,
        pagination=pagination,
        busca=busca
    )

@bp.route("/fitcell/fornecedores/novo", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "criar")
def fitcell_novo_fornecedor():

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
        return redirect(url_for("routes.fitcell_listar_fornecedores"))

    return render_template(
        "fitcell/fornecedor_form.html",
        form=form,
        titulo="Novo Fornecedor"
    )


@bp.route("/fitcell/fornecedores/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "editar")
def fitcell_editar_fornecedor(id):

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
        return redirect(url_for("routes.fitcell_listar_fornecedores"))

    return render_template(
        "fitcell/fornecedor_form.html",
        form=form,
        titulo="Editar Fornecedor"
    )

### ESTOQUE  ####
from datetime import datetime

@bp.route("/fitcell/compras/estoque")
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "ver")
def fitcell_listar_compras_estoque():

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

    # =========================
    # FILTROS
    # =========================
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
        "fitcell/compras_estoque_listar.html",
        compras=compras,
        fornecedores=fornecedores,
        fornecedor_id=fornecedor_id,
        status=status,
        data_ini=data_ini,
        data_fim=data_fim
    )


@bp.route("/fitcell/compras/estoque/<int:id>")
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "ver")
def fitcell_ver_compra_estoque(id):

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
        "fitcell/compra_estoque_detalhe.html",
        compra=compra,
        itens=itens,
        total_compra=total_compra
    )

from datetime import datetime
from flask import request, make_response, render_template
from weasyprint import HTML
from sqlalchemy import func

@bp.route("/fitcell/relatorios/compras-estoque/pdf")
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "ver")
def fitcell_relatorio_compras_estoque_pdf():

    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")
    fornecedor_id = request.args.get("fornecedor_id")

    query = (
        db.session.query(
            CompraEstoque.id,
            CompraEstoque.criado_em,
            Fornecedor.nome.label("fornecedor"),
            CompraEstoque.status,
            func.sum(
                CompraEstoqueItem.quantidade *
                CompraEstoqueItem.custo_unitario
            ).label("total_compra")
        )
        .join(Fornecedor, Fornecedor.id == CompraEstoque.fornecedor_id)
        .join(CompraEstoqueItem, CompraEstoqueItem.compra_id == CompraEstoque.id)
        .filter(CompraEstoque.empresa_id == current_user.empresa_id)
        .group_by(
            CompraEstoque.id,
            CompraEstoque.criado_em,
            Fornecedor.nome,
            CompraEstoque.status
        )
    )

    # =========================
    # FILTROS
    # =========================
    if fornecedor_id:
        query = query.filter(CompraEstoque.fornecedor_id == fornecedor_id)

    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    if dt_ini:
        query = query.filter(CompraEstoque.criado_em >= dt_ini)
    if dt_fim:
        query = query.filter(CompraEstoque.criado_em <= dt_fim)

    compras = query.order_by(CompraEstoque.criado_em.desc()).all()

    # =========================
    # TOTAIS
    # =========================
    total_ativo = sum(
        c.total_compra or 0
        for c in compras
        if c.status != "ESTORNADA"
    )

    total_estornado = sum(
        c.total_compra or 0
        for c in compras
        if c.status == "ESTORNADA"
    )

    html = render_template(
        "fitcell/relatorios/compras_estoque_pdf.html",
        compras=compras,
        total_ativo=total_ativo,
        total_estornado=total_estornado,
        data_ini=data_ini,
        data_fim=data_fim
    )

    pdf = HTML(
        string=html,
        base_url=request.url_root
    ).write_pdf()

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        "inline; filename=compras_estoque.pdf"
    )

    return response

@bp.route("/fitcell/compras/estoque/<int:compra_id>/estornar", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "editar")
def fitcell_estornar_compra_estoque(compra_id):

    compra = (
        CompraEstoque.query_empresa()
        .filter_by(id=compra_id)
        .first_or_404()
    )

    if compra.status == "ESTORNADA":
        flash("Esta compra já foi estornada.", "warning")
        return redirect(url_for("routes.fitcell_listar_compras_estoque"))

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
        return redirect(url_for("routes.fitcell_listar_compras_estoque"))

    # =========================
    # 🔴 VALIDAÇÃO CRÍTICA
    # =========================
    for mov in movimentacoes:

        estoque = (
            EstoquePeca.query_empresa()
            .filter_by(peca_id=mov.peca_id)
            .first()
        )

        qtd_estoque = estoque.quantidade if estoque else 0

        if qtd_estoque < mov.quantidade:
            flash(
                f"Não é possível estornar a compra. "
                f"A peça ID {mov.peca_id} - {mov.peca.nome} já possui vendas associadas.",
                "danger"
            )
            return redirect(url_for("routes.fitcell_listar_compras_estoque"))

    # =========================
    # ✅ ESTORNO SEGURO
    # =========================
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
    return redirect(url_for("routes.fitcell_listar_compras_estoque"))


@bp.route("/fitcell/estoque/movimentacoes")
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "ver")
def fitcell_listar_movimentacoes_estoque():

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
        "fitcell/estoque_movimentacoes_listar.html",
        movimentacoes=pagination.items,
        pagination=pagination,
        busca=busca,
        tipo=tipo
    )


@bp.route("/fitcell/compras/estoque/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("estoque", "criar")
def fitcell_nova_compra_estoque():

    form = CompraEstoqueForm()

    # fornecedores ativos
    form.fornecedor_id.choices = [
        (f.id, f.nome)
        for f in (
            Fornecedor.query_empresa()
            .filter_by(ativo=True)
            .order_by(Fornecedor.nome)
            .all()
        )
    ]

    # peças (para o JS montar select2)
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
            flash("Adicione pelo menos uma peça na compra.", "danger")
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
                    compra_id=compra.id,   # 👈 ESSENCIAL
                    tipo="entrada",
                    quantidade=quantidade,
                    observacao=f"Compra #{compra.id}",
                    criado_em=utc_now()
                )
            )

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

            estoque.quantidade += quantidade

        db.session.commit()

        flash("Compra registrada com sucesso!", "success")
        return redirect(url_for("routes.fitcell_nova_compra_estoque"))


    return render_template(
        "fitcell/compras_estoque_form.html",
        form=form,
        pecas=pecas
    )


### VENDA PEÇA MANUAL ####

from datetime import datetime
from sqlalchemy import func

@bp.route("/fitcell/vendas/pecas")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_listar_vendas_pecas():

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
        "fitcell/vendas_peca_listar.html",
        vendas=pagination.items,
        pagination=pagination,
        busca=busca,
        data_ini=data_ini,
        data_fim=data_fim
    )


@bp.route("/fitcell/vendas/pecas/receber-pix", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "criar")
def fitcell_receber_via_pix():

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

    email_cliente = (
        f"cliente{venda.id}@{current_user.empresa.slug}.com"
    )

    pagamento = mp.criar_pagamento(
        valor=venda.valor_total,
        descricao=f"Venda FITCELL #{venda.id}",
        email=email_cliente
    )

    venda.pagamento_id = str(pagamento["id"])
    venda.pagamento_status = pagamento["status"]

    pix = pagamento["point_of_interaction"]["transaction_data"]
    venda.pix_qr_code = pix["qr_code"]
    venda.pix_qr_code_base64 = pix["qr_code_base64"]

    db.session.commit()

    return redirect(
        url_for("routes.fitcell_ver_venda_peca", id=venda.id)
    )

@bp.route("/fitcell/vendas/pecas/<int:id>/status")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_status_venda_peca(id):

    venda = (
        VendaPeca.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    return {
        "status": venda.status,
        "pagamento_status": venda.pagamento_status,
        "tipo_pagamento": venda.tipo_pagamento,
        "pix_qr_code_base64": venda.pix_qr_code_base64,
        "pix_qr_code": venda.pix_qr_code
    }


@bp.route("/fitcell/vendas/pecas/<int:id>")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_ver_venda_peca(id):

    venda = (
        VendaPeca.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    return render_template(
        "fitcell/vendas_peca_detalhe.html",
        venda=venda
    )


@bp.route("/fitcell/vendas/pecas/nova", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "criar")
def fitcell_nova_venda_peca():

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
            url_for("routes.fitcell_ver_venda_peca", id=venda.id)
        )


    return render_template(
        "fitcell/vendas_peca_form.html",
        form=form,
        pecas=pecas
    )

@bp.route("/fitcell/vendas/pecas/<int:id>/cancelar", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "excluir")
def fitcell_cancelar_venda_peca(id):

    venda = (
        VendaPeca.query_empresa()
        .filter_by(id=id)
        .first_or_404()
    )

    if venda.status == "CANCELADA":
        flash("Essa venda já está cancelada.", "warning")
        return redirect(
            url_for("routes.fitcell_ver_venda_peca", id=id)
        )

    # ==========================
    # ESTORNO DE ESTOQUE
    # ==========================
    for item in venda.itens:

        # movimentação de devolução
        db.session.add(
            EstoqueMovimentacao(
                empresa_id=current_user.empresa_id,
                peca_id=item.peca_id,
                tipo="devolucao",
                quantidade=item.quantidade,
                observacao=f"Estorno venda #{venda.id}",
                criado_em=utc_now()
            )
        )

        # atualiza estoque
        estoque = (
            EstoquePeca.query_empresa()
            .filter_by(peca_id=item.peca_id)
            .first()
        )

        if not estoque:
            estoque = EstoquePeca(
                empresa_id=current_user.empresa_id,
                peca_id=item.peca_id,
                quantidade=0
            )
            db.session.add(estoque)

        estoque.quantidade += item.quantidade

    # ==========================
    # STATUS DA VENDA
    # ==========================
    venda.status = "CANCELADA"

    db.session.commit()

    flash("Venda cancelada e estoque estornado com sucesso.", "success")
    return redirect(
        url_for("routes.fitcell_ver_venda_peca", id=id)
    )


from flask import make_response, render_template, request
from weasyprint import HTML

@bp.route("/fitcell/vendas/pecas/<int:venda_id>/pdf")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_venda_peca_pdf(venda_id):

    venda = (
        VendaPeca.query_empresa()
        .filter_by(id=venda_id)
        .first_or_404()
    )

    html = render_template(
        "fitcell/relatorios/venda_peca_recibo_pdf.html",
        venda=venda
    )

    pdf = HTML(
        string=html,
        base_url=request.url_root
    ).write_pdf()

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f"inline; filename=recibo_venda_{venda.id}.pdf"
    )

    return response


from datetime import datetime, date, timedelta
from flask import request, make_response, render_template
from weasyprint import HTML

@bp.route("/fitcell/relatorios/vendas-pecas/pdf")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_relatorio_vendas_pecas_pdf():

    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    query = (
        VendaPeca.query_empresa()
        .order_by(VendaPeca.criado_em.desc())
    )

    # =========================================
    # FILTRO DE DATA (SOMENTE SE INFORMADO)
    # =========================================
    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    if dt_ini:
        query = query.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        query = query.filter(VendaPeca.criado_em <= dt_fim)

    vendas = query.all()

    # ===============================
    # TOTAIS
    # ===============================
    total_bruto = sum(v.valor_total + v.desconto for v in vendas)
    total_descontos = sum(v.desconto for v in vendas)
    total_liquido = sum(v.valor_total for v in vendas)

    html = render_template(
        "fitcell/relatorios/vendas_pecas_pdf.html",
        vendas=vendas,
        total_bruto=total_bruto,
        total_descontos=total_descontos,
        total_liquido=total_liquido,
        data_ini=data_ini,
        data_fim=data_fim
    )

    pdf = HTML(
        string=html,
        base_url=request.url_root
    ).write_pdf()

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        "inline; filename=vendas_pecas.pdf"
    )

    return response


from datetime import datetime
from flask import request, make_response, render_template
from weasyprint import HTML
from sqlalchemy import func

@bp.route("/fitcell/relatorios/compra-venda/pdf")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_relatorio_compra_venda_pdf():

    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    # =========================
    # TOTAL DE VENDAS
    # =========================
    q_vendas = (
        db.session.query(
            func.coalesce(func.sum(VendaPeca.valor_total), 0)
        )
        .filter(
            VendaPeca.empresa_id == current_user.empresa_id,
            VendaPeca.status.in_(STATUS_FINANCEIRO_VALIDO)
        )
    )

    if dt_ini:
        q_vendas = q_vendas.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        q_vendas = q_vendas.filter(VendaPeca.criado_em <= dt_fim)

    total_vendas = q_vendas.scalar() or 0

    # =========================
    # TOTAL DE COMPRAS (CUSTO)
    # =========================
    q_compras = (
        db.session.query(
            func.coalesce(
                func.sum(
                    CompraEstoqueItem.quantidade *
                    CompraEstoqueItem.custo_unitario
                ),
                0
            )
        )
        .join(CompraEstoque)
        .filter(
            CompraEstoque.empresa_id == current_user.empresa_id,
            CompraEstoque.status != "ESTORNADA"
        )
    )

    if dt_ini:
        q_compras = q_compras.filter(CompraEstoque.criado_em >= dt_ini)
    if dt_fim:
        q_compras = q_compras.filter(CompraEstoque.criado_em <= dt_fim)

    total_compras = q_compras.scalar() or 0

    # =========================
    # LUCRO BRUTO
    # =========================
    lucro_bruto = total_vendas - total_compras

    margem = 0
    if total_vendas > 0:
        margem = (lucro_bruto / total_vendas) * 100

    # =========================
    # RENDER PDF
    # =========================
    html = render_template(
        "fitcell/relatorios/compra_venda_pdf.html",
        total_vendas=total_vendas,
        total_compras=total_compras,
        lucro_bruto=lucro_bruto,
        margem=margem,
        data_ini=data_ini,
        data_fim=data_fim
    )

    pdf = HTML(
        string=html,
        base_url=request.url_root
    ).write_pdf()

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        "inline; filename=lucro_bruto_compra_venda.pdf"
    )

    return response


#### DASHBOARD FITCELL   ###


from datetime import date, timedelta
from flask import request, render_template

@bp.route("/fitcell/bi/dashboard", methods=["GET"])
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_bi_dashboard():

    hoje = date.today()

    data_ini = request.args.get(
        "data_ini",
        (hoje - timedelta(days=30)).strftime("%Y-%m-%d")
    )

    data_fim = request.args.get(
        "data_fim",
        hoje.strftime("%Y-%m-%d")
    )

    return render_template(
        "fitcell/bi/dashboard.html",
        data_ini=data_ini,
        data_fim=data_fim
    )


from sqlalchemy import func
from flask import jsonify

from sqlalchemy import func
from app.constants import STATUS_FINANCEIRO_VALIDO

@bp.route("/fitcell/bi/kpis")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_bi_kpis():

    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    # ==========================
    # 🔹 QUANTIDADE VENDIDA (ITENS)
    # ==========================
    q_qtd = (
        db.session.query(
            func.coalesce(func.sum(VendaPecaItem.quantidade), 0)
        )
        .join(VendaPeca, VendaPeca.id == VendaPecaItem.venda_id)
        .filter(
            VendaPeca.empresa_id == current_user.empresa_id,
            VendaPeca.status.in_(STATUS_FINANCEIRO_VALIDO)
        )
    )

    if dt_ini:
        q_qtd = q_qtd.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        q_qtd = q_qtd.filter(VendaPeca.criado_em <= dt_fim)

    qtd_vendida = q_qtd.scalar() or 0

    # ==========================
    # 🔹 VALOR VENDIDO (JÁ COM DESCONTO)
    # ==========================
    q_valor = (
        VendaPeca.query_empresa()
        .filter(VendaPeca.status.in_(STATUS_FINANCEIRO_VALIDO))
    )

    if dt_ini:
        q_valor = q_valor.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        q_valor = q_valor.filter(VendaPeca.criado_em <= dt_fim)

    valor_vendido = (
        q_valor.with_entities(
            func.coalesce(func.sum(VendaPeca.valor_total), 0)
        )
        .scalar()
    )

    # ==========================
    # 🔹 ESTOQUE ATUAL
    # ==========================
    qtd_estoque = (
        EstoquePeca.query_empresa()
        .with_entities(func.coalesce(func.sum(EstoquePeca.quantidade), 0))
        .scalar()
    )

    valor_estoque = (
        db.session.query(
            func.coalesce(
                func.sum(EstoquePeca.quantidade * Peca.preco_venda),
                0
            )
        )
        .join(Peca, Peca.id == EstoquePeca.peca_id)
        .filter(EstoquePeca.empresa_id == current_user.empresa_id)
        .scalar()
    )

    return jsonify({
        "qtd_vendida": int(qtd_vendida),
        "valor_vendido": formatar_moeda(valor_vendido),
        "qtd_estoque": int(qtd_estoque or 0),
        "valor_estoque": formatar_moeda(valor_estoque),
    })



from sqlalchemy import func
from flask import jsonify
from sqlalchemy.sql import text

from sqlalchemy import func, text
from app.utils import formatar_data

@bp.route("/fitcell/bi/vendido-por-dia")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_bi_vendido_por_dia():

    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    # convertendo UTC para America/SP
    
    dia_br = func.date(
    VendaPeca.criado_em.op("AT TIME ZONE")("America/Sao_Paulo")
    )

    q = (
        db.session.query(
            dia_br.label("dia"),
            func.sum(VendaPeca.valor_total).label("total")
        )
        .filter(
            VendaPeca.empresa_id == current_user.empresa_id,
            VendaPeca.status.in_(STATUS_FINANCEIRO_VALIDO)
        )
    )

    if dt_ini:
        q = q.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        q = q.filter(VendaPeca.criado_em <= dt_fim)

    q = q.group_by(dia_br).order_by(dia_br)

    return jsonify([
        {
            "dia": formatar_data(dia),
            "total": float(total or 0)
        }
        for dia, total in q.all()
    ])


from sqlalchemy import func
from flask import jsonify, request

@bp.route("/fitcell/bi/top-pecas")
@login_required
@requer_licenca_ativa
@requer_permissao("administrativo", "ver")
def fitcell_bi_top_pecas():

    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    q = (
        db.session.query(
            Peca.codigo_interno,
            Peca.nome,
            Peca.imagem,
            func.sum(VendaPecaItem.quantidade).label("quantidade")
        )
        .join(VendaPecaItem, VendaPecaItem.peca_id == Peca.id)
        .join(VendaPeca, VendaPeca.id == VendaPecaItem.venda_id)
        .filter(
            VendaPeca.empresa_id == current_user.empresa_id,
            VendaPeca.status.in_(STATUS_FINANCEIRO_VALIDO),
            Peca.codigo_interno.isnot(None)
        )
    )

    if dt_ini:
        q = q.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        q = q.filter(VendaPeca.criado_em <= dt_fim)

    q = (
        q.group_by(Peca.codigo_interno, Peca.nome, Peca.imagem)
        .order_by(func.sum(VendaPecaItem.quantidade).desc())
        .limit(5)
    )

    return jsonify([
        {
            "codigo": codigo,
            "nome": nome,
            "imagem": imagem,
            "quantidade": int(qtd)
        }
        for codigo, nome, imagem, qtd in q.all()
    ])


from datetime import datetime, date, time
from sqlalchemy import func
from flask import jsonify

@bp.route("/fitcell/bi/home-kpis")
@login_required
@requer_licenca_ativa
def fitcell_bi_home_kpis():

    # 🔐 Apenas admin da empresa
    if not current_user.is_admin_empresa:
        return jsonify({})

    hoje = date.today()

    dt_ini_br = datetime.combine(hoje, time.min)
    dt_fim_br = datetime.combine(hoje, time.max)

    dt_ini = br_to_utc(dt_ini_br)
    dt_fim = br_to_utc(dt_fim_br)


    # =================================================
    # 🔹 VENDAS HOJE
    # =================================================

    # Quantidade vendida (soma dos itens)
    qtd_vendida = (
        db.session.query(
            func.coalesce(func.sum(VendaPecaItem.quantidade), 0)
        )
        .join(VendaPeca, VendaPeca.id == VendaPecaItem.venda_id)
        .filter(
            VendaPeca.empresa_id == current_user.empresa_id,
            VendaPeca.status.in_(STATUS_FINANCEIRO_VALIDO),
            VendaPeca.criado_em >= dt_ini,
            VendaPeca.criado_em <= dt_fim
        )
        .scalar()
    )

    # Valor vendido (já com desconto, valor_final)
    valor_vendido = (
        db.session.query(
            func.coalesce(func.sum(VendaPeca.valor_total), 0)
        )
        .filter(
            VendaPeca.empresa_id == current_user.empresa_id,
            VendaPeca.status.in_(STATUS_FINANCEIRO_VALIDO),
            VendaPeca.criado_em >= dt_ini,
            VendaPeca.criado_em <= dt_fim
        )
        .scalar()
    )

    # =================================================
    # 🔹 ESTOQUE ATUAL (INDEPENDENTE DE DATA)
    # =================================================

    qtd_estoque = (
        EstoquePeca.query_empresa()
        .with_entities(func.coalesce(func.sum(EstoquePeca.quantidade), 0))
        .scalar()
    )

    valor_estoque = (
        db.session.query(
            func.coalesce(
                func.sum(EstoquePeca.quantidade * Peca.preco_venda),
                0
            )
        )
        .join(Peca, Peca.id == EstoquePeca.peca_id)
        .filter(
            EstoquePeca.empresa_id == current_user.empresa_id
        )
        .scalar()
    )

    return jsonify({
        "qtd_vendida": int(qtd_vendida or 0),
        "valor_vendido": formatar_moeda(valor_vendido or 0),
        "qtd_estoque": int(qtd_estoque or 0),
        "valor_estoque": formatar_moeda(valor_estoque or 0),
    })


####### CRM ORCAMENTO  ###

from datetime import datetime
from sqlalchemy import func

@bp.route("/fitcell/orcamentos")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_listar_orcamentos():

    page = request.args.get("page", 1, type=int)
    busca = request.args.get("busca", "")
    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    # =========================
    # QUERY BASE
    # =========================
    query = (
        db.session.query(
            VendaPeca,
            func.coalesce(func.sum(VendaPecaItem.quantidade), 0).label("qtd_itens")
        )
        .outerjoin(VendaPecaItem, VendaPecaItem.venda_id == VendaPeca.id)
        .filter(
            VendaPeca.empresa_id == current_user.empresa_id,
            VendaPeca.status == "ORCAMENTO"
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
    # FILTRO DE DATAS
    # =========================
    dt_ini, dt_fim = periodo_datetime(data_ini, data_fim)

    if dt_ini:
        query = query.filter(VendaPeca.criado_em >= dt_ini)
    if dt_fim:
        query = query.filter(VendaPeca.criado_em <= dt_fim)


    # =========================
    # PAGINAÇÃO
    # =========================
    pagination = query.paginate(page=page, per_page=20)

    return render_template(
        "fitcell/orcamentos_listar.html",
        orcamentos=pagination.items,
        pagination=pagination,
        busca=busca,
        data_ini=data_ini,
        data_fim=data_fim
    )

@bp.route("/fitcell/orcamentos/<int:id>")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_ver_orcamento(id):

    orcamento = (
        VendaPeca.query_empresa()
        .filter_by(id=id, status="ORCAMENTO")
        .first_or_404()
    )

    return render_template(
        "fitcell/orcamento_peca_detalhe.html",
        venda=orcamento
    )


@bp.route("/fitcell/orcamentos/novo", methods=["GET", "POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "criar")
def fitcell_novo_orcamento():

    form = VendaPecaForm()

    # modelos
    form.modelo_celular_id.choices = [
        (m.id, f"{m.marca.nome} {m.nome}".strip())
        for m in ModeloCelular.query_empresa()
        .filter_by(ativo=True)
        .order_by(ModeloCelular.nome)
        .all()
    ]

    pecas = []
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
            .all()
        )

    if request.method == "POST" and form.validate():

        pecas_ids = request.form.getlist("peca_id[]")
        quantidades = request.form.getlist("quantidade[]")
        valores = request.form.getlist("valor_unitario[]")

        if not pecas_ids:
            flash("Adicione pelo menos uma peça.", "danger")
            return redirect(request.url)

        orcamento = VendaPeca(
            empresa_id=current_user.empresa_id,
            modelo_celular_id=form.modelo_celular_id.data,
            cliente_nome=form.cliente_nome.data,
            cliente_telefone=form.cliente_telefone.data,
            tipo_pagamento="orcamento",
            desconto=form.desconto.data or 0,
            status="ORCAMENTO",
            origem="whatsapp",
            criado_em=utc_now()
        )

        db.session.add(orcamento)
        db.session.flush()

        total = 0

        for peca_id, qtd, valor in zip(pecas_ids, quantidades, valores):
            quantidade = int(qtd)
            valor_unitario = float(valor)

            if quantidade <= 0:
                continue

            total_item = quantidade * valor_unitario
            total += total_item

            db.session.add(
                VendaPecaItem(
                    venda_id=orcamento.id,
                    peca_id=int(peca_id),
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=total_item
                )
            )

        total -= float(orcamento.desconto or 0)
        orcamento.valor_total = total

        db.session.commit()

        flash("Orçamento criado com sucesso!", "success")
        return redirect(
            url_for("routes.fitcell_ver_orcamento", id=orcamento.id)
        )

    return render_template(
        "fitcell/orcamento_peca_form.html",
        form=form,
        pecas=pecas
    )


from flask import make_response, render_template, request
from weasyprint import HTML

@bp.route("/fitcell/orcamentos/<int:orcamento_id>/pdf")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_orcamento_pdf(orcamento_id):

    orcamento = (
        VendaPeca.query_empresa()
        .filter_by(
            id=orcamento_id,
            status="ORCAMENTO"
        )
        .first_or_404()
    )

    html = render_template(
        "fitcell/relatorios/orcamento_recibo_pdf.html",
        venda=orcamento
    )

    pdf = HTML(
        string=html,
        base_url=request.url_root
    ).write_pdf()

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f"inline; filename=orcamento_{orcamento.id}.pdf"
    )

    return response



from urllib.parse import quote_plus

@bp.route("/fitcell/orcamentos/<int:id>/whatsapp")
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "ver")
def fitcell_enviar_orcamento_whatsapp(id):

    venda = (
        VendaPeca.query_empresa()
        .filter_by(id=id, status="ORCAMENTO")
        .first_or_404()
    )

    linhas = []
    for item in venda.itens:
        linhas.append(
            f"- {item.peca.nome} ({item.quantidade}x) R$ {item.valor_total:.2f}"
        )

    texto = (
        "Olá! Segue seu orçamento:\n\n"
        + "\n".join(linhas)
        + f"\n\nTotal: R$ {venda.valor_total:.2f}\n"
        "Qualquer dúvida é só chamar 🙂"
    )

    texto_url = quote_plus(texto)
    telefone = venda.cliente_telefone.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")

    return redirect(f"https://wa.me/55{telefone}?text={texto_url}")

@bp.route("/fitcell/orcamentos/<int:id>/converter", methods=["POST"])
@login_required
@requer_licenca_ativa
@requer_permissao("venda", "editar")
def fitcell_converter_orcamento(id):

    venda = (
        VendaPeca.query_empresa()
        .filter_by(id=id, status="ORCAMENTO")
        .first_or_404()
    )

    venda.status = "FINALIZADA"
    venda.pago_em = utc_now()
    venda.tipo_pagamento = "dinheiro"

    # aqui você faz a movimentação de estoque
    # exatamente como na venda manual

    db.session.commit()

    flash("Orçamento convertido em venda!", "success")
    return redirect(
        url_for("routes.fitcell_ver_venda_peca", id=id)
    )
