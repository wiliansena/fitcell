
from decimal import Decimal
from typing import Optional
from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DateTimeField, DecimalField, HiddenField, SelectMultipleField, StringField, SubmitField, FloatField, FileField, TextAreaField
from wtforms.validators import DataRequired
from wtforms import SelectField
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, FileField, FieldList, FormField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from datetime import date
from wtforms.validators import DataRequired, Length
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, InputRequired, Length, EqualTo
from wtforms import (
    SelectField,
    IntegerField,
    DecimalField,
    TextAreaField
)
from wtforms.validators import DataRequired, NumberRange, Optional

from flask_wtf import FlaskForm

##### STV #####

##### STV #####

class LicencaSistemaForm(FlaskForm):
    dias_acesso = IntegerField("Dias_De_Acesso", validators=[DataRequired()])
    submit = SubmitField("Salvar")

class UsuarioForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired(), Length(min=3, max=100)])
    senha = PasswordField('Senha', validators=[DataRequired(), Length(min=6, max=100)])
    email = StringField("E-mail",  validators=[DataRequired(), Email(), Length(max=120)])
    confirmar_senha = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('senha', message='As senhas devem coincidir.')])
    submit = SubmitField('Salvar')


class ServicoForm(FlaskForm):
    nome = StringField("Nome do Serviço", validators=[DataRequired()])
    tipo = SelectField(
        "Tipo",
        choices=[
            ("compartilhado", "Compartilhado"),
            ("individual", "Individual"),
        ],validators=[DataRequired()])
    telas_total = IntegerField("Total de Telas", validators=[Optional(), NumberRange(min=1)])
    valor_venda_padrao = DecimalField("Valor Venda Padrão", places=2, validators=[InputRequired()])
    comissao_padrao = DecimalField("Comissão padrão", places=2, validators=[InputRequired()])
    ativo = BooleanField("Ativo")
    imagem = FileField("Imagem do Serviço")

class ContaForm(FlaskForm):
    email = StringField("Email da Conta", validators=[DataRequired(), Email()])
    senha = StringField("Senha", validators=[Optional()]) 
    servico_id = SelectField("Serviço", coerce=int, validators=[DataRequired()])
    valor_venda_override = DecimalField("Venda personalizada (Opcional)", places=2, validators=[Optional()])
    comissao_override = DecimalField("Comissão personalizada (Opcional)", places=2, validators=[Optional()])
    valor_investido = DecimalField("Valor Investido", places=4, validators=[InputRequired()])
    ativa = BooleanField("Conta Ativa")

class VendaStreamingForm(FlaskForm):
    telefone = StringField("Telefone do Cliente", validators=[DataRequired()])

## PAGAMENTO FORM ###

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    BooleanField,
    SelectField,
    SubmitField
)
from wtforms.validators import DataRequired, Length


class EmpresaPagamentoConfigForm(FlaskForm):

    gateway = SelectField(
        "Gateway de Pagamento",
        choices=[
            ("mercadopago", "Mercado Pago"),
        ],
        validators=[DataRequired()]
    )

    access_token = StringField(
        "Access Token",
        validators=[DataRequired(), Length(max=255)]
    )

    public_key = StringField(
        "Public Key",
        validators=[Length(max=255)]
    )

    ativo = BooleanField(
        "Ativar pagamentos automáticos",
        default=True
    )

    submit = SubmitField("Salvar configuração")

#### CELULAR   ########

class MarcaCelularForm(FlaskForm):
    nome = StringField(
        "Marca do Celular",
        validators=[
            DataRequired(),
            Length(max=80)
        ]
    )

    ativo = BooleanField(
        "Ativa",
        default=True
    )

    submit = SubmitField("Salvar")

from wtforms import SelectField


class ModeloCelularForm(FlaskForm):
    marca_id = SelectField(
        "Marca",
        coerce=int,
        validators=[DataRequired()]
    )

    nome = StringField(
        "Modelo",
        validators=[
            DataRequired(),
            Length(max=80)
        ]
    )

    variante = StringField(
        "Variante",
        validators=[
            Length(max=80)
        ],
        description="Ex: 2021, 2022, Pro, Plus"
    )

    ativo = BooleanField(
        "Ativo",
        default=True
    )

    submit = SubmitField("Salvar")


class TipoPecaForm(FlaskForm):

    nome = StringField(
        "Tipo de Peça",
        validators=[
            DataRequired(),
            Length(max=50)
        ]
    )
    submit = SubmitField("Salvar")
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SelectField,
    DecimalField,
    BooleanField,
    TextAreaField,
    SelectMultipleField
)
from wtforms.validators import DataRequired, Optional
from app.models import TipoPeca, ModeloCelular

class PecaForm(FlaskForm):

    nome = StringField("Nome da Peça")

    tipo_peca_id = SelectField(
        "Tipo da Peça",
        coerce=int,
        validators=[DataRequired()]
    )

    qualidade = SelectField(
        "Qualidade",
        choices=[
            ("original", "Original"),
            ("premium", "Premium"),
            ("compativel", "Compatível")
        ],
        validators=[DataRequired()]
    )

    preco_venda = DecimalField(
        "Preço de Venda",
        validators=[DataRequired()]
    )

    preco_minimo = DecimalField(
        "Preço Mínimo",
        validators=[Optional()]
    )

    codigo_interno = StringField("Código Interno")
    marca_peca = StringField("Marca da Peça")

    observacoes = TextAreaField("Observações")
    imagem = FileField("Imagem da Peça")

    ativo = BooleanField("Ativo", default=True)

    # 🔥 USADO SOMENTE NO EDITAR
    modelos_compativeis = SelectMultipleField(
        "Modelos Compatíveis",
        coerce=int,
        validators=[Optional()]
    )

    def carregar_choices(self, empresa_id):
        self.tipo_peca_id.choices = [
            (t.id, t.nome)
            for t in TipoPeca.query.order_by(TipoPeca.nome).all()
        ]

        self.modelos_compativeis.choices = [
            (m.id, f"{m.marca.nome} {m.nome} {m.variante or ''}".strip())
            for m in (
                ModeloCelular.query
                .filter_by(empresa_id=empresa_id, ativo=True)
                .order_by(ModeloCelular.nome)
                .all()
            )
        ]


from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    IntegerField,
    DecimalField,
    StringField,
    HiddenField
)
from wtforms.validators import DataRequired, NumberRange, Optional


class VendaPecaForm(FlaskForm):

    modelo_celular_id = SelectField(
        "Modelo do Celular",
        coerce=int,
        validators=[DataRequired()]
    )

    cliente_nome = StringField(
        "Nome do Cliente",
        validators=[Optional()]
    )

    cliente_telefone = StringField(
        "Telefone",
        validators=[Optional()]
    )

    tipo_pagamento = SelectField(
        "Forma de Pagamento",
        choices=[
            ("dinheiro", "Dinheiro"),
            ("pix", "Pix"),
            ("cartao", "Cartão")
        ],
        validators=[DataRequired()]
    )

    desconto = DecimalField(
        "Desconto",
        default=0,
        validators=[Optional()]
    )

    submit = SubmitField("Finalizar Venda")



class FornecedorForm(FlaskForm):

    nome = StringField(
        "Nome",
        validators=[DataRequired(), Length(max=150)]
    )

    tipo = SelectField(
        "Tipo",
        choices=[
            ("PF", "Pessoa Física"),
            ("PJ", "Pessoa Jurídica"),
        ],
        default="PF",
        validators=[DataRequired()]
    )

    documento = StringField(
        "Documento",
        validators=[Optional(), Length(max=20)]
    )

    telefone = StringField(
        "Telefone",
        validators=[Optional(), Length(max=30)]
    )

    email = StringField(
        "E-mail",
        validators=[Optional(), Length(max=120)]
    )

    observacoes = TextAreaField(
        "Observações",
        validators=[Optional()]
    )

    ativo = BooleanField("Ativo", default=True)

class CompraEstoqueForm(FlaskForm):

    fornecedor_id = SelectField(
        "Fornecedor",
        coerce=int,
        validators=[DataRequired()]
    )

    observacao = TextAreaField(
        "Observações"
    )