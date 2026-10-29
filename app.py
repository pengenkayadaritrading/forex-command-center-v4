"""Forex Command Center V4: cloud-hosted, per-user report dashboard (no broker login)."""
import io
import os
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, session, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import UniqueConstraint

app = Flask(__name__)
secret = os.environ.get('SECRET_KEY')
if not secret or len(secret) < 32:
    raise RuntimeError('Set SECRET_KEY to a random value of at least 32 characters.')
database_url = os.environ.get('DATABASE_URL', 'sqlite:///v4_local.db')
if database_url.startswith('postgres://'):
    database_url = 'postgresql+psycopg://' + database_url[len('postgres://'):]
elif database_url.startswith('postgresql://'):
    database_url = 'postgresql+psycopg://' + database_url[len('postgresql://'):]
app.config.update(SECRET_KEY=secret, SQLALCHEMY_DATABASE_URI=database_url, SQLALCHEMY_TRACK_MODIFICATIONS=False, MAX_CONTENT_LENGTH=4*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','1')=='1')
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    deal_id = db.Column(db.String(80), nullable=False)
    time = db.Column(db.DateTime(timezone=True), nullable=False)
    symbol = db.Column(db.String(40), nullable=False)
    side = db.Column(db.String(8), nullable=False)
    volume = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    profit = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False, default=0)
    swap = db.Column(db.Float, nullable=False, default=0)
    fee = db.Column(db.Float, nullable=False, default=0)
    __table_args__ = (UniqueConstraint('user_id','deal_id',name='unique_user_deal'),)

class Candle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    symbol = db.Column(db.String(40), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False)
    time = db.Column(db.DateTime(timezone=True), nullable=False)
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Float, nullable=False, default=0)
    __table_args__ = (UniqueConstraint('user_id','symbol','timeframe','time',name='unique_user_candle'),)

with app.app_context():
    db.create_all()

@app.before_request
def csrf_protect():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    if request.method == 'POST' and not secrets.compare_digest(request.form.get('csrf',''),session['csrf']):
        abort(400, 'Invalid CSRF token')

@app.context_processor
def inject_csrf():
    return {'csrf': session.get('csrf','')}

def logged_in(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not session.get('uid'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return inner

def current_user():
    return db.session.get(User, session['uid'])

@app.route('/')
def index():
    return redirect(url_for('dashboard') if session.get('uid') else url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        if not (5 <= len(email) <= 254 and '@' in email and len(password)>=12):
            flash('Email valid dan password minimal 12 karakter diperlukan.','error')
        elif User.query.filter_by(email=email).first():
            flash('Email sudah terdaftar.','error')
        else:
            user = User(email=email, password_hash=generate_password_hash(password))
            db.session.add(user); db.session.commit()
            session.clear(); session['uid']=user.id; session['csrf']=secrets.token_urlsafe(32)
            return redirect(url_for('dashboard'))
    return render_template('auth.html', title='Daftar', register=True)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
        if user and check_password_hash(user.password_hash,request.form.get('password','')):
            session.clear(); session['uid']=user.id; session['csrf']=secrets.token_urlsafe(32)
            return redirect(url_for('dashboard'))
        flash('Email atau password salah.','error')
    return render_template('auth.html', title='Masuk', register=False)

@app.route('/logout', methods=['POST'])
@logged_in
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@logged_in
def dashboard():
    trades = Trade.query.filter_by(user_id=session['uid']).order_by(Trade.time.desc()).limit(500).all()
    candles = Candle.query.filter_by(user_id=session['uid'],symbol='XAUUSD').order_by(Candle.time.desc()).limit(500).all()
    candles = list(reversed(candles))
    pnl = sum(t.profit+t.commission+t.swap+t.fee for t in trades)
    wins = sum(1 for t in trades if t.profit+t.commission+t.swap+t.fee > 0)
    fig_data = {'x':[c.time.isoformat() for c in candles], 'open':[c.open for c in candles], 'high':[c.high for c in candles], 'low':[c.low for c in candles], 'close':[c.close for c in candles]}
    return render_template('dashboard.html', user=current_user(), trades=trades, candles=candles, fig_data=fig_data, pnl=pnl, wins=wins)

REQUIRED_TRADES = {'deal_id','time','symbol','side','volume','price','profit'}
REQUIRED_CANDLES = {'time','open','high','low','close'}

def read_csv():
    f = request.files.get('file')
    if not f or not f.filename.lower().endswith('.csv'):
        raise ValueError('Pilih file .csv')
    raw = f.read()
    if len(raw)>4*1024*1024:
        raise ValueError('File maksimal 4 MB')
    for encoding in ('utf-8-sig','utf-16','cp1252'):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding, sep=None, engine='python')
        except (UnicodeError, pd.errors.ParserError):
            continue
    raise ValueError('CSV tidak dapat dibaca')

def as_dt(value):
    ts = pd.to_datetime(value, utc=True, errors='raise')
    return ts.to_pydatetime().replace(tzinfo=None)

@app.route('/upload/trades', methods=['POST'])
@logged_in
def upload_trades():
    try:
        df=read_csv(); df.columns=[str(c).strip().lower() for c in df.columns]
        if not REQUIRED_TRADES.issubset(df.columns):
            raise ValueError('Kolom wajib: '+', '.join(sorted(REQUIRED_TRADES)))
        if len(df)>10000: raise ValueError('Maksimal 10.000 baris per file')
        added=0
        for _,r in df.iterrows():
            deal_id=str(r['deal_id']).strip()
            if not deal_id: continue
            if Trade.query.filter_by(user_id=session['uid'],deal_id=deal_id).first(): continue
            side=str(r['side']).upper().strip()
            if side not in ('BUY','SELL'): continue
            db.session.add(Trade(user_id=session['uid'],deal_id=deal_id,time=as_dt(r['time']),symbol=str(r['symbol'])[:40],side=side,volume=float(r['volume']),price=float(r['price']),profit=float(r['profit']),commission=float(r.get('commission',0) or 0),swap=float(r.get('swap',0) or 0),fee=float(r.get('fee',0) or 0)))
            added+=1
        db.session.commit(); flash(f'{added} deal berhasil diimpor.','ok')
    except (ValueError, TypeError, OverflowError, KeyError) as e:
        db.session.rollback(); flash(f'Gagal impor: {e}','error')
    return redirect(url_for('dashboard'))

@app.route('/upload/candles', methods=['POST'])
@logged_in
def upload_candles():
    try:
        df=read_csv(); df.columns=[str(c).strip().lower() for c in df.columns]
        if not REQUIRED_CANDLES.issubset(df.columns):
            raise ValueError('Kolom wajib: '+', '.join(sorted(REQUIRED_CANDLES)))
        if len(df)>10000: raise ValueError('Maksimal 10.000 baris per file')
        symbol=str(request.form.get('symbol','XAUUSD')).upper().strip()[:40]
        timeframe=str(request.form.get('timeframe','M15')).upper().strip()[:10]
        if symbol != 'XAUUSD' or timeframe not in ('M1','M5','M15','M30','H1','H4','D1'):
            raise ValueError('Gunakan symbol XAUUSD dan timeframe valid')
        added=0
        for _,r in df.iterrows():
            t=as_dt(r['time'])
            if Candle.query.filter_by(user_id=session['uid'],symbol=symbol,timeframe=timeframe,time=t).first(): continue
            o,h,l,c=(float(r[k]) for k in ('open','high','low','close'))
            if not (l<=min(o,c)<=max(o,c)<=h): raise ValueError('OHLC tidak valid')
            db.session.add(Candle(user_id=session['uid'],symbol=symbol,timeframe=timeframe,time=t,open=o,high=h,low=l,close=c,volume=float(r.get('volume',0) or 0)))
            added+=1
        db.session.commit(); flash(f'{added} candle berhasil diimpor.','ok')
    except (ValueError, TypeError, OverflowError, KeyError) as e:
        db.session.rollback(); flash(f'Gagal impor: {e}','error')
    return redirect(url_for('dashboard'))

@app.route('/delete-data',methods=['POST'])
@logged_in
def delete_data():
    Trade.query.filter_by(user_id=session['uid']).delete()
    Candle.query.filter_by(user_id=session['uid']).delete()
    db.session.commit()
    flash('Data trading milikmu telah dihapus.','ok')
    return redirect(url_for('dashboard'))

@app.route('/health')
def health():
    return {'status':'ok'}

if __name__=='__main__':
    app.run(debug=False)
