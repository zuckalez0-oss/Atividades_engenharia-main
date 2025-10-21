import os
import json
import uuid
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, abort, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- CONFIGURAÇÃO ---
basedir = os.path.abspath(os.path.dirname(__file__))
usuarios_json_path = os.path.join(basedir, 'usuarios.json.bkp') # Apontando para o backup

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-trocar-em-producao'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'atividades.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_BASE_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER_ATIVIDADES'] = os.path.join(UPLOAD_BASE_FOLDER, 'atividades')
app.config['UPLOAD_FOLDER_PEDIDOS'] = os.path.join(UPLOAD_BASE_FOLDER, 'pedidos')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx', 'txt'}

os.makedirs(app.config['UPLOAD_FOLDER_ATIVIDADES'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_PEDIDOS'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"


# --- FUNÇÕES AUXILIARES ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# --- MODELOS DE DADOS (com User no DB) ---
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    # user_id é a chave primária (id) da tabela User
    return User.query.get(int(user_id))

class Atividade(db.Model):
    __tablename__ = 'atividade'
    id = db.Column(db.Integer, primary_key=True)
    nome_atividade = db.Column(db.String(200), nullable=False)
    prioridade = db.Column(db.String(10), nullable=False, default='P-3')
    imagem_anexo = db.Column(db.String(100), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    centro_de_custo = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Iniciado')
    responsavel_atual = db.Column(db.String(150), nullable=False)
    pedido = db.Column(db.String(100), nullable=True)
    local_de_entrega = db.Column(db.String(200), nullable=True)
    solicitante = db.Column(db.String(150), nullable=True)
    obra_destino = db.Column(db.String(200), nullable=True)
    historico = db.relationship('HistoricoModificacao', backref='atividade', lazy=True, cascade="all, delete-orphan", order_by='desc(HistoricoModificacao.data_modificacao)')

class HistoricoModificacao(db.Model):
    __tablename__ = 'historico_modificacao'
    id = db.Column(db.Integer, primary_key=True)
    data_modificacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    campo_alterado = db.Column(db.String(100), nullable=False)
    valor_antigo = db.Column(db.Text, nullable=True)
    valor_novo = db.Column(db.Text, nullable=True)
    modificado_por = db.Column(db.String(150), nullable=False)
    atividade_id = db.Column(db.Integer, db.ForeignKey('atividade.id'), nullable=False)

class PedidoProducao(db.Model):
    __tablename__ = 'pedido_producao'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    pedido = db.Column(db.String(100), nullable=True)
    data_termino_producao = db.Column(db.Date, nullable=True)
    data_prevista_entrega = db.Column(db.Date, nullable=True)
    centro_de_custo = db.Column(db.String(100), nullable=True)
    solicitante = db.Column(db.String(150), nullable=True)
    destino = db.Column(db.String(200), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    anexo_imagem_filename = db.Column(db.String(100), nullable=True)
    anexo_arquivo_filename = db.Column(db.String(100), nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    criado_por = db.Column(db.String(150), nullable=False)


# --- ROTAS DA APLICAÇÃO ---

@app.route('/uploads/<folder>/<path:filename>')
def uploaded_file(folder, filename):
    if folder == 'atividades':
        return send_from_directory(app.config['UPLOAD_FOLDER_ATIVIDADES'], filename)
    elif folder == 'pedidos':
        return send_from_directory(app.config['UPLOAD_FOLDER_PEDIDOS'], filename)
    else:
        abort(404)

@app.route('/')
@login_required
def index():
    ultimas_atividades = Atividade.query.order_by(Atividade.data_criacao.desc()).limit(5).all()
    ultimos_pedidos = PedidoProducao.query.order_by(PedidoProducao.data_criacao.desc()).limit(5).all()
    return render_template('index.html', ultimas_atividades=ultimas_atividades, ultimos_pedidos=ultimos_pedidos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        login_input = request.form.get('login')
        senha_input = request.form.get('senha')
        user_obj = User.query.filter_by(login=login_input).first()
        if user_obj and check_password_hash(user_obj.senha_hash, senha_input):
            login_user(user_obj)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Login ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado com sucesso.', 'success')
    return redirect(url_for('login'))

# --- ROTAS DE ATIVIDADES DE ENGENHARIA ---

@app.route('/atividades')
@login_required
def todas_atividades():
    atividades_em_andamento = Atividade.query.filter(Atividade.status != 'Concluído').order_by(Atividade.prioridade, Atividade.data_criacao.desc()).all()
    atividades_concluidas = Atividade.query.filter(Atividade.status == 'Concluído').order_by(Atividade.data_criacao.desc()).all()
    return render_template('atividades.html', atividades_em_andamento=atividades_em_andamento, atividades_concluidas=atividades_concluidas)

@app.route('/atividade/nova', methods=['GET', 'POST'])
@login_required
def nova_atividade():
    if request.method == 'POST':
        nome_arquivo_salvo = None
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                nome_arquivo_salvo = f"ativ_{uuid.uuid4()}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_ATIVIDADES'], nome_arquivo_salvo))
        
        nova = Atividade(
            nome_atividade=request.form.get('nome_atividade'),
            prioridade=request.form.get('prioridade'),
            centro_de_custo=request.form.get('centro_de_custo'),
            observacoes=request.form.get('observacoes'),
            pedido=request.form.get('pedido'),
            local_de_entrega=request.form.get('local_de_entrega'),
            solicitante=request.form.get('solicitante'),
            obra_destino=request.form.get('obra_destino'),
            responsavel_atual=current_user.nome,
            imagem_anexo=nome_arquivo_salvo
        )
        db.session.add(nova)
        db.session.commit()
        
        hist_criacao = HistoricoModificacao(campo_alterado="Criação da Atividade", valor_novo=f"Atividade '{nova.nome_atividade}' criada.", modificado_por=current_user.nome, atividade_id=nova.id)
        db.session.add(hist_criacao)
        if nome_arquivo_salvo:
            hist_anexo = HistoricoModificacao(campo_alterado="Anexo", valor_novo="Imagem adicionada.", modificado_por=current_user.nome, atividade_id=nova.id)
            db.session.add(hist_anexo)
        
        db.session.commit()
        flash('Atividade criada com sucesso!', 'success')
        return redirect(url_for('todas_atividades'))
    return render_template('form_atividade.html', title="Nova Atividade de Engenharia")

@app.route('/atividade/<int:atividade_id>')
@login_required
def detalhes_atividade(atividade_id):
    atividade = Atividade.query.get_or_404(atividade_id)
    return render_template('detalhes_atividade.html', atividade=atividade)

@app.route('/atividade/<int:atividade_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_atividade(atividade_id):
    atividade = Atividade.query.get_or_404(atividade_id)
    if request.method == 'POST':
        campos_modificados = []
        
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '' and allowed_file(file.filename):
                if atividade.imagem_anexo:
                    caminho_antigo = os.path.join(app.config['UPLOAD_FOLDER_ATIVIDADES'], atividade.imagem_anexo)
                    if os.path.exists(caminho_antigo): os.remove(caminho_antigo)
                
                ext = file.filename.rsplit('.', 1)[1].lower()
                nome_arquivo_salvo = f"ativ_{uuid.uuid4()}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_ATIVIDADES'], nome_arquivo_salvo))
                
                campos_modificados.append(('Anexo', atividade.imagem_anexo, nome_arquivo_salvo))
                atividade.imagem_anexo = nome_arquivo_salvo

        campos_para_verificar = {
            'nome_atividade': 'Nome da Atividade', 'prioridade': 'Prioridade',
            'centro_de_custo': 'Centro de Custo', 'status': 'Status', 
            'observacoes': 'Observações', 'pedido': 'Pedido',
            'local_de_entrega': 'Local de Entrega', 'solicitante': 'Solicitante',
            'obra_destino': 'Obra / Destino'
        }
        for attr, nome_campo in campos_para_verificar.items():
            valor_antigo, valor_novo = getattr(atividade, attr), request.form.get(attr)
            if str(valor_antigo or '') != str(valor_novo or ''):
                campos_modificados.append((nome_campo, valor_antigo, valor_novo))
                setattr(atividade, attr, valor_novo)
        
        if campos_modificados:
            atividade.responsavel_atual = current_user.nome
            for campo, antigo, novo in campos_modificados:
                historico = HistoricoModificacao(campo_alterado=campo, valor_antigo=antigo, valor_novo=novo, modificado_por=current_user.nome, atividade_id=atividade.id)
                db.session.add(historico)
            db.session.commit()
            flash('Atividade atualizada com sucesso!', 'success')
        else:
            flash('Nenhuma alteração foi feita.', 'info')
        return redirect(url_for('detalhes_atividade', atividade_id=atividade.id))
    return render_template('form_atividade.html', title="Editar Atividade de Engenharia", atividade=atividade)

@app.route('/atividade/<int:atividade_id>/excluir', methods=['POST'])
@login_required
def excluir_atividade(atividade_id):
    if not current_user.is_admin:
        abort(403)
    atividade = Atividade.query.get_or_404(atividade_id)
    if atividade.imagem_anexo:
        caminho_img = os.path.join(app.config['UPLOAD_FOLDER_ATIVIDADES'], atividade.imagem_anexo)
        if os.path.exists(caminho_img): os.remove(caminho_img)
    db.session.delete(atividade)
    db.session.commit()
    flash(f'Atividade #{atividade.id} foi excluída com sucesso.', 'success')
    return redirect(url_for('todas_atividades'))

# --- ROTAS DE PEDIDOS DE PRODUÇÃO ---

@app.route('/pedidos')
@login_required
def todos_pedidos():
    pedidos = PedidoProducao.query.order_by(PedidoProducao.data_criacao.desc()).all()
    return render_template('pedidos.html', pedidos=pedidos)

@app.route('/pedido/novo', methods=['GET', 'POST'])
@login_required
def novo_pedido():
    if request.method == 'POST':
        imagem_salva, arquivo_salvo = None, None
        
        if 'anexo_imagem' in request.files:
            file = request.files['anexo_imagem']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                imagem_salva = f"img_{uuid.uuid4()}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_PEDIDOS'], imagem_salva))

        if 'anexo_arquivo' in request.files:
            file = request.files['anexo_arquivo']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                arquivo_salvo = f"file_{uuid.uuid4()}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_PEDIDOS'], arquivo_salvo))

        data_termino_str = request.form.get('data_termino_producao')
        data_termino = date.fromisoformat(data_termino_str) if data_termino_str else None
        data_entrega_str = request.form.get('data_prevista_entrega')
        data_entrega = date.fromisoformat(data_entrega_str) if data_entrega_str else None

        novo = PedidoProducao(
            nome=request.form.get('nome'),
            pedido=request.form.get('pedido'),
            data_termino_producao=data_termino,
            data_prevista_entrega=data_entrega,
            centro_de_custo=request.form.get('centro_de_custo'),
            solicitante=request.form.get('solicitante'),
            destino=request.form.get('destino'),
            observacoes=request.form.get('observacoes'),
            anexo_imagem_filename=imagem_salva,
            anexo_arquivo_filename=arquivo_salvo,
            criado_por=current_user.nome
        )
        db.session.add(novo)
        db.session.commit()
        flash('Pedido de Produção criado com sucesso!', 'success')
        return redirect(url_for('todos_pedidos'))

    return render_template('form_pedido.html', title="Novo Pedido de Produção")

@app.route('/pedido/<int:pedido_id>')
@login_required
def detalhes_pedido(pedido_id):
    pedido = PedidoProducao.query.get_or_404(pedido_id)
    return render_template('detalhes_pedido.html', pedido=pedido)


# --- INICIALIZAÇÃO E FUNÇÕES FINAIS ---
@app.context_processor
def inject_year():
    return {'current_year': datetime.utcnow().year}

def migrar_usuarios_json_para_db():
    """
    Lê o arquivo JSON de usuários (se existir) e os insere no banco de dados.
    Gera hash para senhas em texto plano e evita duplicatas.
    Esta função deve ser executada uma vez.
    """
    try:
        if not os.path.exists(usuarios_json_path):
            print("Arquivo de backup de usuários (usuarios.json.bkp) não encontrado. Pulando migração.")
            return

        with open(usuarios_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for user_data in data.get('usuarios', []):
            login = user_data.get('login')
            if not login:
                continue

            # Verifica se o usuário já existe
            if User.query.filter_by(login=login).first():
                print(f"Usuário '{login}' já existe no banco de dados. Pulando.")
                continue

            # Garante que a senha tenha hash
            senha_hash = user_data.get('senha_hash')
            if not senha_hash and 'senha' in user_data:
                senha_hash = generate_password_hash(user_data['senha'], method='pbkdf2:sha256')

            if not senha_hash:
                print(f"Usuário '{login}' sem senha ou hash. Pulando.")
                continue

            novo_usuario = User(
                login=login,
                nome=user_data.get('nome'),
                senha_hash=senha_hash,
                is_admin=user_data.get('is_admin', False)
            )
            db.session.add(novo_usuario)
            print(f"Usuário '{login}' migrado para o banco de dados.")
        
        db.session.commit()
        print("Migração de usuários concluída.")

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Erro ao processar o arquivo de usuários JSON: {e}")

def inicializar_db():
    """Cria as tabelas e executa a migração inicial de usuários se necessário."""
    with app.app_context():
        db.create_all()
        # A função de migração será executada se a tabela de usuários estiver vazia.
        if not User.query.first():
            print("Tabela de usuários vazia. Tentando migrar de 'usuarios.json.bkp'...")
            migrar_usuarios_json_para_db()
        else:
            print("Tabela de usuários já contém dados. Migração não necessária.")

# Bloco para execução local
if __name__ == '__main__':
    inicializar_db()
    app.run(debug=True)
