from decimal import Decimal
from flask_login import UserMixin
from sqlalchemy.orm import relationship
from app import db
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from datetime import datetime
from sqlalchemy.orm import backref
from app.mixins import EmpresaQueryMixin
from app.utils_datetime import utc_now

from datetime import date, timedelta

 ####   USUÁRIO    ######
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Empresa(db.Model):
    __tablename__ = "empresa"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cnpj = db.Column(db.String(18), unique=True, nullable=True)
    slug = db.Column(db.String(80), nullable=False, index=True)  # DEFINIR EMPRESA NO PAG AUTOMATICO
    email = db.Column(db.String(255))

    ativa = db.Column(db.Boolean, default=True)
    criada_em = db.Column(db.DateTime, default=utc_now)


class Usuario(UserMixin, EmpresaQueryMixin,db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=True   # 👈 MASTER NÃO TEM EMPRESA
    )

    empresa = db.relationship(
        "Empresa",
        backref="usuarios"
    )

    is_master = db.Column(db.Boolean, default=False)  # 👈 CHAVE DO PAINEL MASTER
    is_admin_empresa = db.Column(db.Boolean, default=False)
    tipo = db.Column(db.String(100), nullable=True)

    nome = db.Column(db.String(100), nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    # termos de uso #
    termos_aceitos = db.Column(db.Boolean, default=False)
    data_aceite_termos = db.Column(db.DateTime)
    versao_termos = db.Column(db.String(20))
    ip_aceite = db.Column(db.String(45))

    permissoes = db.relationship(
        "Permissao",
        backref="usuario",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def todas_permissoes(self):
        return {(p.categoria, p.acao) for p in self.permissoes.all()}

    def tem_permissao(self, categoria, acao):
        return (categoria, acao) in self.todas_permissoes

    def pode_trocar_senha(self):
        return self.tem_permissao("trocar_senha", "editar")


class Permissao(EmpresaQueryMixin, db.Model ):
    __tablename__ = "permissao"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id"),
        nullable=False
    )

    categoria = db.Column(db.String(50), nullable=False)
    acao = db.Column(db.String(20), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "usuario_id",
            "categoria",
            "acao",
            name="unique_permissao_usuario_empresa"
        ),
    )

class LogAcao(EmpresaQueryMixin, db.Model):
    __tablename__ = "log_acao"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id"),
        nullable=False
    )

    usuario_nome = db.Column(db.String(100), nullable=False)
    acao = db.Column(db.String(255), nullable=False)

    data_hora = db.Column(
        db.DateTime,
        default=utc_now)

    usuario = db.relationship("Usuario")


class LicencaSistema(EmpresaQueryMixin, db.Model):
    __tablename__ = "licenca_sistema"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False
    )
    empresa = db.relationship("Empresa")

    data_inicio = db.Column(db.Date, nullable=False, default=date.today)
    dias_acesso = db.Column(db.Integer, nullable=False, default=1)

    @property
    def data_fim(self):
        return self.data_inicio + timedelta(days=self.dias_acesso)

    @property
    def dias_restantes(self):
        hoje = utc_now().date()
        return max((self.data_fim - hoje).days, 0)

    @property
    def expirado(self):
        return self.dias_restantes <= 0


class EmpresaPagamentoConfig(db.Model):
    __tablename__ = "empresa_pagamento_config"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        unique=True,
        nullable=False
    )

    empresa = db.relationship("Empresa")

    # ---------------------------------
    # GATEWAY
    # ---------------------------------
    gateway = db.Column(
        db.String(30),
        nullable=False,
        default="mercadopago"
    )
    # mercadopago | efi | stripe (futuro)

    # ---------------------------------
    # MERCADO PAGO
    # ---------------------------------
    access_token = db.Column(
        db.String(255),
        nullable=False
    )

    public_key = db.Column(db.String(255))
    webhook_secret = db.Column(db.String(255))

    ativo = db.Column(db.Boolean, default=True)

    criado_em = db.Column(db.DateTime, default=utc_now)



class Cliente(EmpresaQueryMixin, db.Model):
    __tablename__ = "cliente"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    # =================================================
    # IDENTIFICAÇÃO
    # =================================================
    nome = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), index=True)
    telefone = db.Column(db.String(20), index=True)

    documento = db.Column(db.String(20), index=True)
    # CPF / CNPJ (sem validação aqui)

    tipo = db.Column(
        db.String(20),
        default="PF"
    )
    # PF | PJ

    # =================================================
    # ENDEREÇO (OPCIONAL)
    # =================================================
    cep = db.Column(db.String(10))
    endereco = db.Column(db.String(255))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))

    # =================================================
    # CONTROLE
    # =================================================
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=utc_now)

    # 🔹 NOVO RELACIONAMENTO (VENDA NOVA)
    vendas = db.relationship(
        "Venda",
        back_populates="cliente",
        lazy="dynamic"
    )

    # 🔹 LEGADO (STREAMING) — SEM back_populates
    vendas_streaming = db.relationship(
        "VendaStreaming",
        lazy="dynamic"
    )



#### CELULAR   #####
class MarcaCelular(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_marca_celular"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    nome = db.Column(db.String(80), nullable=False)
    ativo = db.Column(db.Boolean, default=True)

    criado_em = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "nome",
            name="uq_fitcell_marca_empresa_nome"
        ),
    )


class ModeloCelular(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_modelo_celular"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    marca_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_marca_celular.id"),
        nullable=False
    )
    marca = db.relationship("MarcaCelular")

    nome = db.Column(db.String(80), nullable=False)
    variante = db.Column(db.String(80))  # ex: 2021, Pro, Plus
    ativo = db.Column(db.Boolean, default=True)

    criado_em = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "marca_id",
            "nome",
            "variante",
            name="uq_fitcell_modelo_empresa"
        ),
    )

class TipoPeca(db.Model):
    __tablename__ = "fitcell_tipo_peca"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)

class Peca(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_peca"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    tipo_peca_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_tipo_peca.id"),
        nullable=False
    )
    tipo = db.relationship("TipoPeca")

    qualidade = db.Column(
        db.String(30),
        nullable=False
    )
    # original | primeira_linha | compativel

    nome = db.Column(db.String(120))
    preco_venda = db.Column(db.Numeric(10, 2), nullable=False)
    preco_minimo = db.Column(db.Numeric(10, 2), nullable=True)

    codigo_interno = db.Column(db.String(60), index=True)
    marca_peca = db.Column(db.String(80))

    imagem = db.Column(db.String(200), nullable=True)
    observacoes = db.Column(db.Text)

    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=utc_now)


class CompatibilidadePeca(db.Model):
    __tablename__ = "fitcell_compatibilidade_peca"

    id = db.Column(db.Integer, primary_key=True)

    peca_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_peca.id"),
        nullable=False
    )
    peca = db.relationship("Peca")

    modelo_celular_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_modelo_celular.id"),
        nullable=False
    )
    modelo = db.relationship("ModeloCelular")

    __table_args__ = (
        db.UniqueConstraint(
            "peca_id",
            "modelo_celular_id",
            name="uq_fitcell_peca_modelo"
        ),
    )

class EstoquePeca(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_estoque_peca"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    peca_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_peca.id"),
        nullable=False,
        unique=True
    )
    peca = db.relationship("Peca")

    quantidade = db.Column(db.Integer, nullable=False, default=0)


class VendaPeca(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_venda_peca"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    modelo_celular_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_modelo_celular.id"),
        nullable=False
    )
    modelo_celular = db.relationship("ModeloCelular")

    cliente_nome = db.Column(db.String(120))
    cliente_telefone = db.Column(db.String(20))

    tipo_pagamento = db.Column(db.String(20))
    # dinheiro | pix | cartao

    desconto = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    valor_total = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    status = db.Column(
        db.String(30),
        default="FINALIZADA"
    )
    # FINALIZADA | CANCELADA

    origem = db.Column(
        db.String(20),
        default="manual"
    )
    # manual | link

    criado_em = db.Column(db.DateTime, default=utc_now)
    pago_em = db.Column(db.DateTime)

    # PIX (já preparado)
    pix_qr_code = db.Column(db.Text)
    pix_qr_code_base64 = db.Column(db.Text)
    pagamento_id = db.Column(db.String(100))
    pagamento_status = db.Column(db.String(30))

    itens = db.relationship(
        "VendaPecaItem",
        back_populates="venda",
        cascade="all, delete-orphan"
    )

    @property
    def subtotal(self):
        """
        Total da venda sem desconto
        """
        return sum(
            (item.valor_unitario * item.quantidade)
            for item in self.itens
        )

    @property
    def valor_desconto(self):
        return self.desconto or Decimal("0.00")

    @property
    def total_com_desconto(self):
        return self.subtotal - self.valor_desconto

class VendaPecaItem(db.Model):
    __tablename__ = "fitcell_venda_peca_item"

    id = db.Column(db.Integer, primary_key=True)

    venda_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_venda_peca.id"),
        nullable=False,
        index=True
    )

    peca_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_peca.id"),
        nullable=False
    )
    peca = db.relationship("Peca")

    quantidade = db.Column(db.Integer, nullable=False)

    valor_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    valor_total = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    venda = db.relationship(
        "VendaPeca",
        back_populates="itens"
    )


class Fornecedor(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_fornecedor"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    nome = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), index=True)
    tipo = db.Column(db.String(20), default="PF") # PF | PJ
    telefone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    observacoes = db.Column(db.Text)

    ativo = db.Column(db.Boolean, default=True)

    criado_em = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "nome",
            name="uq_fitcell_fornecedor_empresa_nome"
        ),
    )
class CompraEstoque(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_compra_estoque"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    fornecedor_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_fornecedor.id"),
        nullable=False
    )
    fornecedor = db.relationship("Fornecedor")

    observacao = db.Column(db.Text)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="ATIVA"
    )
    # ATIVA | ESTORNADA

    criado_em = db.Column(db.DateTime, default=utc_now)
    estornada_em = db.Column(db.DateTime)


class CompraEstoqueItem(db.Model):
    __tablename__ = "fitcell_compra_estoque_item"

    id = db.Column(db.Integer, primary_key=True)

    compra_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_compra_estoque.id"),
        nullable=False
    )

    peca_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_peca.id"),
        nullable=False
    )
    peca = db.relationship("Peca")

    quantidade = db.Column(db.Integer, nullable=False)
    custo_unitario = db.Column(db.Numeric(10, 2), nullable=False)

class EstoqueMovimentacao(EmpresaQueryMixin, db.Model):
    __tablename__ = "fitcell_estoque_movimentacao"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    peca_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_peca.id"),
        nullable=False
    )
    peca = db.relationship("Peca")

    fornecedor_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_fornecedor.id"),
        nullable=True,
        index=True
    )
    fornecedor = db.relationship("Fornecedor")

    compra_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_compra_estoque.id"),
        nullable=True,
        index=True
    )

    tipo = db.Column(
        db.String(30),
        nullable=False
    )
    # entrada | saida | ajuste | defeito | devolucao | estorno

    movimentacao_origem_id = db.Column(
        db.Integer,
        db.ForeignKey("fitcell_estoque_movimentacao.id"),
        nullable=True
    )

    quantidade = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=utc_now)
