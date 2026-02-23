import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from supabase import create_client
import time

st.set_page_config(page_title="Gestion Copropriété", page_icon="🏢", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 2rem; }
    .stat-box { background: #f0f2f6; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ==================== FORMULAIRE PUBLIC LOCATAIRES ====================
# Détection du paramètre ?fiche=TOKEN dans l'URL
_qp = st.query_params
if "fiche" in _qp:
    import hashlib, json as _json, urllib.request as _ureq, urllib.parse as _uparse

    _token = _qp["fiche"]

    # Retrouver la fiche via le token
    def _get_fiche_by_token(token):
        try:
            r = supabase.table('fiches_tokens').select('*').eq('token', token).eq('actif', True).execute()
            return r.data[0] if r.data else None
        except:
            return None

    _fiche = _get_fiche_by_token(_token)

    st.markdown("""
    <style>
    #MainMenu, header, footer, [data-testid="stSidebar"] { display: none !important; }
    .block-container { max-width: 700px !important; margin: 0 auto; padding-top: 2rem; }
    </style>
    """, unsafe_allow_html=True)

    if _fiche is None:
        st.error("❌ Ce lien est invalide ou a expiré.")
        st.info("Contactez votre syndic pour obtenir un nouveau lien.")
        st.stop()

    _prop_nom  = _fiche.get('proprietaire_nom','')
    _prop_id   = _fiche.get('proprietaire_nom','')  # nom utilisé comme clé

    # Charger tous les lots de ce propriétaire
    try:
        _lots_r = supabase.table('coproprietaires').select('*').eq('nom', _prop_nom).execute()
        _lots   = _lots_r.data or []
    except:
        _lots = []

    # En-tête
    st.markdown(f"""
    <div style="text-align:center;margin-bottom:2rem;">
      <div style="font-size:2.5rem;">🏢</div>
      <h2 style="color:#1f77b4;">Fiche Locataire</h2>
      <p style="color:#aaa;">Copropriété — Mise à jour annuaire</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"Bonjour **{_prop_nom.split('(')[0].strip()}**,")
    st.markdown("Merci de renseigner les informations de vos locataires actuels. "
                "Ces données nous permettront de mettre à jour les **boîtes aux lettres** "
                "et l'**interphone** de la résidence.")
    st.divider()

    USAGE_LABELS = {
        'parking':'🅿️ Parking','studio':'🏠 Studio','studio ':'🏠 Studio',
        '2pieces':'🏠 2 pièces','2 pieces':'🏠 2 pièces',
        '2 pieces duplex':'🏠 2 pièces duplex','3 pieces':'🏠 3 pièces',
        '3 pieces duplex':'🏠 3 pièces duplex',
    }

    _appts = [l for l in _lots if 'parking' not in str(l.get('usage','')).lower()]
    _pks   = [l for l in _lots if 'parking' in str(l.get('usage','')).lower()]

    if not _appts and not _pks:
        st.warning("Aucun lot trouvé pour ce propriétaire.")
        st.stop()

    with st.form("form_public_fiche"):
        _responses = []

        if _appts:
            st.markdown("### 🏠 Appartement(s)")
            for _lot in _appts:
                _lot_num = _lot.get('lot','?')
                _etage   = _lot.get('etage','?')
                _usage   = USAGE_LABELS.get(str(_lot.get('usage','')).strip().lower(),
                                            str(_lot.get('usage','')))
                _lot_id  = int(_lot['id'])

                st.markdown(f"**{_usage} — Lot {_lot_num} — {_etage}**")
                _c1, _c2 = st.columns(2)
                with _c1:
                    _occ = st.radio(f"Occupation lot {_lot_num}",
                                    ["J'occupe moi-même", "Loué"],
                                    key=f"occ_{_lot_id}", horizontal=True)
                    _l_prenom = st.text_input("Prénom du locataire", key=f"lp_{_lot_id}")
                    _l_nom    = st.text_input("Nom du locataire",    key=f"ln_{_lot_id}")
                with _c2:
                    _l_email = st.text_input("Email du locataire",  key=f"le_{_lot_id}")
                    _l_tel   = st.text_input("Téléphone",           key=f"lt_{_lot_id}")
                    _l_bal   = st.text_input("Étiquette BAL souhaitée",
                                             key=f"lb_{_lot_id}",
                                             placeholder=f"Ex: DUPONT — Lot {_lot_num}",
                                             help="Nom à inscrire sur la boîte aux lettres")
                    _l_iph   = st.text_input("Étiquette Interphone",
                                             key=f"li_{_lot_id}",
                                             placeholder="Ex: DUPONT",
                                             help="Nom à afficher sur l'interphone")
                st.divider()
                _responses.append({
                    'lot_id': _lot_id, 'lot_num': _lot_num,
                    'occupation': _occ,
                    'prenom': _l_prenom, 'nom': _l_nom,
                    'email': _l_email, 'telephone': _l_tel,
                    'label_bal': _l_bal, 'label_interphone': _l_iph,
                    'is_parking': False,
                })

        if _pks:
            st.markdown("### 🅿️ Parking(s)")
            for _lot in _pks:
                _lot_num = _lot.get('lot','?')
                _etage   = _lot.get('etage','?')
                _lot_id  = int(_lot['id'])
                st.markdown(f"**🅿️ Parking — Lot {_lot_num} — {_etage}**")
                _pk_occ = st.radio(f"Parking lot {_lot_num}",
                                   ["J'utilise moi-même", "Loué à quelqu'un"],
                                   key=f"pk_{_lot_id}", horizontal=True)
                if _pk_occ == "Loué à quelqu'un":
                    _pk_nom = st.text_input("Nom du locataire parking", key=f"pkn_{_lot_id}")
                else:
                    _pk_nom = ""
                _responses.append({
                    'lot_id': _lot_id, 'lot_num': _lot_num,
                    'occupation': _pk_occ, 'nom': _pk_nom, 'prenom': '',
                    'email': '', 'telephone': '', 'label_bal': '', 'label_interphone': '',
                    'is_parking': True,
                })

        _notes_gen = st.text_area("💬 Remarques éventuelles", key="notes_gen", height=80)
        _submit    = st.form_submit_button("✅ Envoyer ma fiche", type="primary",
                                           use_container_width=True)

    if _submit:
        try:
            _today = pd.Timestamp.today().strftime('%Y-%m-%d')
            _saved = 0
            for _r in _responses:
                if _r['is_parking']:
                    continue  # Les parkings : info simple, pas de locataire à enregistrer
                _is_loue = _r['occupation'] == 'Loué'
                if _is_loue and _r['nom'].strip():
                    # Désactiver l'ancien locataire actif si existant
                    _ex = supabase.table('locataires').select('id').eq(
                        'lot_id', _r['lot_id']).eq('actif', True).execute()
                    for _ex_row in (_ex.data or []):
                        supabase.table('locataires').update(
                            {'actif': False, 'date_sortie': _today}
                        ).eq('id', _ex_row['id']).execute()
                    # Insérer le nouveau locataire
                    supabase.table('locataires').insert({
                        'lot_id':            _r['lot_id'],
                        'prenom':            _r['prenom'].strip() or None,
                        'nom':               _r['nom'].strip(),
                        'email':             _r['email'].strip() or None,
                        'telephone':         _r['telephone'].strip() or None,
                        'label_bal':         _r['label_bal'].strip() or None,
                        'label_interphone':  _r['label_interphone'].strip() or None,
                        'date_entree':       _today,
                        'actif':             True,
                        'notes':             _notes_gen.strip() or None,
                    }).execute()
                    _saved += 1

            # Marquer le token comme utilisé
            supabase.table('fiches_tokens').update(
                {'utilise': True}
            ).eq('token', _token).execute()

            st.success("✅ Merci ! Vos informations ont bien été enregistrées.")
            st.balloons()
            st.info("Vous pouvez fermer cette page. Le syndic a été notifié.")

            # Notifier le syndic par email si Brevo configuré
            try:
                _brevo_key  = st.secrets.get("brevo_api_key","")
                _brevo_from = st.secrets.get("brevo_from_email","")
                if _brevo_key and _brevo_from:
                    import json as _j2
                    _prop_court = _prop_nom.split('(')[0].strip()
                    _date_envoi = pd.Timestamp.today().strftime('%d/%m/%Y à %H:%M')

                    # ── Corps texte ─────────────────────────────────
                    _body_txt = (
                        f"FICHE LOCATAIRE REÇUE\n"
                        f"{'='*40}\n"
                        f"Propriétaire : {_prop_nom}\n"
                        f"Date de réponse : {_date_envoi}\n\n"
                    )

                    # ── Corps HTML ──────────────────────────────────
                    _rows_html = ""
                    for _r in _responses:
                        _is_loue = _r['occupation'] in ('Loué', "Loué à quelqu'un")
                        _usage_r = '🅿️ Parking' if _r['is_parking'] else '🏠 Appartement'
                        _statut_r = '🏠 Loué' if _is_loue else '👤 Occupé propriétaire'
                        _bg = '#e8f5e9' if _is_loue else '#f5f5f5'

                        if _is_loue and (_r.get('nom','').strip() or _r['is_parking']):
                            _nom_loc    = f"{_r.get('prenom','')} {_r.get('nom','')}".strip()
                            _email_loc  = _r.get('email','—') or '—'
                            _tel_loc    = _r.get('telephone','—') or '—'
                            _bal_loc    = _r.get('label_bal','—') or '—'
                            _iph_loc    = _r.get('label_interphone','—') or '—'

                            _body_txt += (
                                f"LOT {_r['lot_num']} — {_usage_r}\n"
                                f"  Statut      : {_statut_r}\n"
                                f"  Locataire   : {_nom_loc}\n"
                                f"  Email       : {_email_loc}\n"
                                f"  Téléphone   : {_tel_loc}\n"
                                f"  BAL         : {_bal_loc}\n"
                                f"  Interphone  : {_iph_loc}\n\n"
                            )
                            _rows_html += f"""
                            <tr style="background:{_bg};">
                              <td style="padding:8px;border:1px solid #ddd;"><b>Lot {_r['lot_num']}</b></td>
                              <td style="padding:8px;border:1px solid #ddd;">{_usage_r}</td>
                              <td style="padding:8px;border:1px solid #ddd;">{_statut_r}</td>
                              <td style="padding:8px;border:1px solid #ddd;"><b>{_nom_loc}</b></td>
                              <td style="padding:8px;border:1px solid #ddd;"><a href="mailto:{_email_loc}">{_email_loc}</a></td>
                              <td style="padding:8px;border:1px solid #ddd;"><a href="tel:{_tel_loc}">{_tel_loc}</a></td>
                              <td style="padding:8px;border:1px solid #ddd;">{_bal_loc}</td>
                              <td style="padding:8px;border:1px solid #ddd;">{_iph_loc}</td>
                            </tr>"""
                        else:
                            _body_txt += (
                                f"LOT {_r['lot_num']} — {_usage_r}\n"
                                f"  Statut : {_statut_r}\n\n"
                            )
                            _rows_html += f"""
                            <tr style="background:{_bg};">
                              <td style="padding:8px;border:1px solid #ddd;"><b>Lot {_r['lot_num']}</b></td>
                              <td style="padding:8px;border:1px solid #ddd;">{_usage_r}</td>
                              <td colspan="6" style="padding:8px;border:1px solid #ddd;color:#888;">{_statut_r}</td>
                            </tr>"""

                    if _notes_gen.strip():
                        _body_txt += f"Notes : {_notes_gen}\n"

                    _body_html = f"""
                    <html><body style="font-family:Arial,sans-serif;color:#333;">
                      <div style="background:#1f77b4;padding:16px;border-radius:8px 8px 0 0;">
                        <h2 style="color:white;margin:0;">📋 Fiche locataire reçue</h2>
                      </div>
                      <div style="border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;">
                        <p><b>Propriétaire :</b> {_prop_nom}</p>
                        <p><b>Date de réponse :</b> {_date_envoi}</p>
                        <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:0.9em;">
                          <thead>
                            <tr style="background:#1f77b4;color:white;">
                              <th style="padding:8px;text-align:left;">Lot</th>
                              <th style="padding:8px;text-align:left;">Type</th>
                              <th style="padding:8px;text-align:left;">Statut</th>
                              <th style="padding:8px;text-align:left;">Locataire</th>
                              <th style="padding:8px;text-align:left;">Email</th>
                              <th style="padding:8px;text-align:left;">Téléphone</th>
                              <th style="padding:8px;text-align:left;">BAL</th>
                              <th style="padding:8px;text-align:left;">Interphone</th>
                            </tr>
                          </thead>
                          <tbody>{_rows_html}</tbody>
                        </table>
                        {"<p><b>Notes :</b> " + _notes_gen + "</p>" if _notes_gen.strip() else ""}
                        <p style="margin-top:20px;color:#888;font-size:0.85em;">
                          ✅ Ces informations ont été enregistrées automatiquement dans Supabase.
                        </p>
                      </div>
                    </body></html>"""

                    _payload = _j2.dumps({
                        "sender": {"name": "Copropriété", "email": _brevo_from},
                        "to":     [{"email": _brevo_from}],
                        "subject": f"📋 Fiche locataire — {_prop_court} — {_date_envoi}",
                        "textContent": _body_txt,
                        "htmlContent": _body_html,
                    }).encode('utf-8')
                    _req2 = _ureq.Request("https://api.brevo.com/v3/smtp/email",
                        data=_payload,
                        headers={"accept":"application/json","content-type":"application/json",
                                 "api-key":_brevo_key}, method="POST")
                    _ureq.urlopen(_req2)
            except:
                pass

        except Exception as _e:
            st.error(f"❌ Erreur lors de l'enregistrement : {_e}")

    st.stop()  # Ne pas afficher le reste de l'app

# v20260218_111053 — Fix Alur base = total_bud
# ==================== FONCTIONS DB ====================
def get_budget():
    try:
        return pd.DataFrame(supabase.table('budget').select('*').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur budget: {e}"); return pd.DataFrame()

def get_depenses(date_debut=None, date_fin=None):
    try:
        q = supabase.table('depenses').select('*')
        if date_debut: q = q.gte('date', date_debut.strftime('%Y-%m-%d'))
        if date_fin:   q = q.lte('date', date_fin.strftime('%Y-%m-%d'))
        df = pd.DataFrame(q.execute().data)
        if not df.empty and 'deleted' in df.columns:
            df = df[df['deleted'] != True]
        return df
    except Exception as e:
        st.error(f"❌ Erreur dépenses: {e}"); return pd.DataFrame()

def upload_facture(dep_id, file_bytes, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    storage_path = f"depenses/{dep_id}/{filename}"
    content_type = 'application/pdf' if ext == 'pdf' else f'image/{ext}'
    supabase.storage.from_('factures').upload(
        storage_path, file_bytes,
        file_options={"content-type": content_type, "upsert": "true"}
    )
    supabase.table('depenses').update({'facture_path': storage_path}).eq('id', dep_id).execute()
    return storage_path

def get_facture_url(storage_path):
    """Retourne l'URL signée (1h) de la facture."""
    try:
        r = supabase.storage.from_('factures').create_signed_url(storage_path, 3600)
        return r.get('signedURL') or r.get('signedUrl', '')
    except:
        return ''

def get_facture_bytes(storage_path):
    """Télécharge les bytes du fichier depuis Supabase Storage."""
    try:
        data = supabase.storage.from_('factures').download(storage_path)
        return bytes(data)
    except:
        return None

def afficher_facture(storage_path, height=600):
    """Affiche PDF via PDF.js (contourne les blocages Chrome) ou image."""
    import base64
    import streamlit.components.v1 as components
    ext = str(storage_path).rsplit('.', 1)[-1].lower()
    file_bytes = get_facture_bytes(storage_path)
    if file_bytes is None:
        st.warning("⚠️ Impossible de charger la facture depuis Supabase.")
        return
    fname = str(storage_path).split('/')[-1]
    mime = 'application/pdf' if ext == 'pdf' else f'image/{ext}'
    # Bouton téléchargement toujours disponible
    st.download_button("⬇️ Télécharger la facture", data=file_bytes,
                       file_name=fname, mime=mime, key=f"dl_{abs(hash(storage_path))}")
    if ext == 'pdf':
        b64 = base64.b64encode(file_bytes).decode('utf-8')
        # PDF.js via CDN — fonctionne sans restriction Chrome
        pdf_html = f"""
<div id="pdf-container" style="width:100%;height:{height}px;border:1px solid #444;
     border-radius:6px;overflow:auto;background:#fff;">
  <canvas id="pdf-canvas"></canvas>
</div>
<div style="margin-top:6px;text-align:center;color:#aaa;font-size:0.85em;">
  Page <span id="cur-page">1</span> / <span id="tot-pages">?</span>
  &nbsp;
  <button onclick="changePage(-1)" style="margin:0 4px;padding:2px 10px;cursor:pointer;">◀</button>
  <button onclick="changePage(1)"  style="margin:0 4px;padding:2px 10px;cursor:pointer;">▶</button>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script>
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
  const pdfData = atob('{b64}');
  const arr = new Uint8Array(pdfData.length);
  for (let i=0;i<pdfData.length;i++) arr[i]=pdfData.charCodeAt(i);
  let pdfDoc=null, curPage=1;
  const canvas=document.getElementById('pdf-canvas');
  const ctx=canvas.getContext('2d');
  function renderPage(n) {{
    pdfDoc.getPage(n).then(page => {{
      const vp = page.getViewport({{scale: 1.5}});
      canvas.width=vp.width; canvas.height=vp.height;
      page.render({{canvasContext:ctx,viewport:vp}});
      document.getElementById('cur-page').textContent=n;
    }});
  }}
  function changePage(d) {{
    const n=curPage+d;
    if(n>=1 && n<=pdfDoc.numPages){{ curPage=n; renderPage(n); }}
  }}
  pdfjsLib.getDocument({{data:arr}}).promise.then(doc=>{{
    pdfDoc=doc;
    document.getElementById('tot-pages').textContent=doc.numPages;
    renderPage(1);
  }});
</script>"""
        components.html(pdf_html, height=height + 50, scrolling=False)
    else:
        st.image(file_bytes, use_container_width=True)

def delete_facture(dep_id, storage_path):
    supabase.storage.from_('factures').remove([storage_path])
    supabase.table('depenses').update({'facture_path': None}).eq('id', dep_id).execute()

def get_coproprietaires():
    try:
        return pd.DataFrame(supabase.table('coproprietaires').select('*').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur copropriétaires: {e}"); return pd.DataFrame()

def get_plan_comptable():
    try:
        return pd.DataFrame(supabase.table('plan_comptable').select('*').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur plan comptable: {e}"); return pd.DataFrame()

def get_travaux_votes():
    try:
        return pd.DataFrame(supabase.table('travaux_votes').select('*').order('date').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur travaux_votes: {e}"); return pd.DataFrame()

def get_travaux_votes_depense_ids():
    """Retourne les IDs des dépenses transférées en travaux votés."""
    try:
        res = supabase.table('travaux_votes').select('depense_id').not_.is_('depense_id', 'null').execute()
        return [r['depense_id'] for r in res.data if r.get('depense_id')]
    except:
        return []

def get_loi_alur():
    try:
        return pd.DataFrame(supabase.table('loi_alur').select('*').order('date').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur loi_alur: {e}"); return pd.DataFrame()

def get_depenses_alur_ids():
    """Retourne les IDs des dépenses déjà affectées au fonds Alur."""
    try:
        res = supabase.table('loi_alur').select('depense_id').not_.is_('depense_id', 'null').execute()
        return [r['depense_id'] for r in res.data if r.get('depense_id')]
    except:
        return []

# ==================== CONFIGURATION CLÉS DE RÉPARTITION ====================
# Basé sur votre plan comptable réel :
# Classe 1A, 1B, 7 → Charges générales → tantième_general / 10 000
# Classe 2          → Électricité RDC/ss-sols → tantième_rdc_ssols / 928
# Classe 3          → Électricité sous-sols → tantième_ssols / 20
# Classe 4          → Garages/Parkings → tantième_garages / 28
# Classe 5          → Ascenseurs → tantième_ascenseurs / 1 000
# Classe 6          → Monte-voitures → tantième_ssols / 20

MAPPING_CLASSE_TANTIEME = {
    '1A': 'general',
    '1B': 'general',
    '7':  'general',
    '2':  'rdc_ssols',
    '3':  'ssols_elec',
    '4':  'garages',
    '5':  'ascenseurs',
    '6':  'ssols',
}

# ==================== CONFIGURATION SYNDIC ====================
SYNDIC_INFO = {
    "nom": "VILLA TOBIAS (0275)",
    "adresse": "52 RUE SMOLETT",
    "cp_ville": "06300 NICE",
    "ville": "NICE",
}

# Libellés des postes pour les PDFs (correspondance clé CHARGES_CONFIG → libellé officiel)
POSTES_LABELS = {
    'general':    'CHARGES COMMUNES GENERALES',
    'ascenseurs': 'ASCENSEURS',
    'rdc_ssols':  'CHARGES SPECIALES RDC S/SOLS',
    'ssols_elec': 'CHARGES SPECIALES S/SOLS',
    'garages':    'CHARGES GARAGES/PARKINGS',
    'ssols':      'MONTE VOITURES',
}

def generate_appel_pdf_bytes(syndic, cop_row, periode, label_trim, annee,
                              montants, alur_par_appel, nb_appels):
    """Génère le PDF d'appel de fonds pour un copropriétaire. Retourne bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from io import BytesIO

    JAUNE      = colors.HexColor('#FFD700')
    JAUNE_CLAIR= colors.HexColor('#FFFACD')
    BLEU       = colors.HexColor('#4472C4')
    GRIS_CLAIR = colors.HexColor('#D9D9D9')

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=15*mm)

    def sty(size=9, bold=False, align='LEFT', color=colors.black):
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        al = {'LEFT': TA_LEFT, 'RIGHT': TA_RIGHT, 'CENTER': TA_CENTER}[align]
        fn = 'Helvetica-Bold' if bold else 'Helvetica'
        return ParagraphStyle('s', fontSize=size, fontName=fn, textColor=color,
                              alignment=al, leading=size*1.3)

    story = []

    # --- EN-TÊTE ---
    from datetime import date
    date_str = date.today().strftime('%d/%m/%Y')
    header = Table([[
        [Paragraph("<u><b>Appel de Fonds</b></u>", sty(20, True)),
         Paragraph(f"Période du {periode}", sty(9))],
        [Paragraph(f"A {syndic['ville']}, le {date_str}", sty(9, align='RIGHT')),
         Paragraph(f"<b>{syndic['nom']}</b>", sty(9, True, 'RIGHT')),
         Paragraph(syndic['adresse'], sty(9, align='RIGHT')),
         Paragraph(syndic['cp_ville'], sty(9, align='RIGHT'))]
    ]], colWidths=[95*mm, 85*mm])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.append(header)
    story.append(Spacer(1, 6*mm))

    # --- BLOC RÉF / DESTINATAIRE ---
    nom_cop  = str(cop_row.get('nom', ''))
    ref_cop  = f"0275-{str(cop_row.get('lot','')).zfill(4)}"
    login    = str(cop_row.get('login', '') or '')
    adresse  = str(cop_row.get('adresse', '') or '')
    cp_ville = str(cop_row.get('cp_ville', '') or '')

    ref_tbl = Table([[
        [Paragraph(f"<b>APPEL DE FONDS TRIMESTRIELS {annee}</b>", sty(9, True)),
         Paragraph(f"Réf : {ref_cop} / {nom_cop}", sty(9)),
         Paragraph(f"Internet Login : {login}  Mot de Passe :", sty(9))],
        [],
        [Paragraph(f"<b>{nom_cop}</b>", sty(9, True)),
         Paragraph(adresse, sty(9)),
         Paragraph(cp_ville, sty(9))]
    ]], colWidths=[80*mm, 20*mm, 80*mm])
    ref_tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.append(ref_tbl)
    story.append(Spacer(1, 8*mm))

    # --- TABLEAU DES POSTES ---
    col_widths = [14*mm, 82*mm, 22*mm, 22*mm, 22*mm, 22*mm]
    thead = [['', Paragraph('Postes à répartir', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Total', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Base', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Tantièmes', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Quote-part', sty(9, True, 'CENTER', colors.white))]]

    lot   = str(cop_row.get('lot',''))
    usage = str(cop_row.get('usage',''))
    rows  = [[Paragraph(f"<b>{lot}</b>", sty(9, True)),
              Paragraph(f"<b>{usage}</b>", sty(9, True)),
              '', '', '', '']]

    total_lot = 0
    for key, cfg in CHARGES_CONFIG.items():
        tant  = float(cop_row.get(cfg['col'], 0) or 0)
        if cfg['total'] == 0 or tant == 0:
            continue
        montant_annuel = montants.get(key, 0)
        quote_part = round((tant / cfg['total']) * (montant_annuel / nb_appels), 2)
        if quote_part == 0:
            continue
        total_lot += quote_part
        rows.append(['',
            Paragraph(POSTES_LABELS.get(key, cfg['label']), sty(8.5)),
            Paragraph(f"{montant_annuel/nb_appels:,.2f}", sty(8.5, align='RIGHT')),
            Paragraph(str(cfg['total']), sty(8.5, align='CENTER')),
            Paragraph(str(int(tant)), sty(8.5, align='CENTER')),
            Paragraph(f"{quote_part:,.2f}", sty(8.5, align='RIGHT'))])

    # Ligne Alur
    tant_gen = float(cop_row.get('tantieme_general', 0) or 0)
    if tant_gen > 0 and alur_par_appel > 0:
        alur_cop = round(tant_gen / 10000 * alur_par_appel, 2)
        total_lot += alur_cop
        rows.append(['',
            Paragraph('FONDS TRAVAUX ALUR', sty(8.5)),
            Paragraph(f"{alur_par_appel:,.2f}", sty(8.5, align='RIGHT')),
            Paragraph('10000', sty(8.5, align='CENTER')),
            Paragraph(str(int(tant_gen)), sty(8.5, align='CENTER')),
            Paragraph(f"{alur_cop:,.2f}", sty(8.5, align='RIGHT'))])

    dont_tva = round(total_lot * 20 / 120, 2)

    rows.append(['', Paragraph('<b>TOTAL DU LOT</b>', sty(9, True, 'RIGHT')),
                 '', '', '',
                 Paragraph(f"<b>{total_lot:,.2f}</b>", sty(9, True, 'RIGHT'))])
    rows.append(['', Paragraph('<b>DONT TVA</b>', sty(9, True, 'RIGHT')),
                 '', '', '',
                 Paragraph(f"<b>{dont_tva:,.2f}</b>", sty(9, True, 'RIGHT'))])

    table_data = thead + rows
    n = len(table_data)
    n_lot = 1; n_ds = 2; n_de = n - 3; n_tot = n - 2; n_tva = n - 1

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_rules = [
        ('BACKGROUND', (0,0), (-1,0), BLEU),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('TOPPADDING', (0,0), (-1,0), 5), ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('BACKGROUND', (0,n_lot), (-1,n_lot), GRIS_CLAIR),
        ('BACKGROUND', (5,n_ds), (5,n_de), GRIS_CLAIR),
        ('BACKGROUND', (0,n_tot), (-1,n_tot), JAUNE),
        ('BACKGROUND', (0,n_tva), (-1,n_tva), JAUNE_CLAIR),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#CCCCCC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#999999')),
        ('ALIGN', (2,1), (2,-1), 'RIGHT'),
        ('ALIGN', (3,1), (3,-1), 'CENTER'),
        ('ALIGN', (4,1), (4,-1), 'CENTER'),
        ('ALIGN', (5,1), (5,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,1), (-1,-1), 3), ('BOTTOMPADDING', (0,1), (-1,-1), 3),
        ('LEFTPADDING', (1,0), (1,-1), 6),
    ]
    for i in range(n_ds, n_tot):
        bg = colors.white if i % 2 == 0 else colors.HexColor('#F5F5F5')
        style_rules.append(('BACKGROUND', (0,i), (4,i), bg))
    tbl.setStyle(TableStyle(style_rules))
    story.append(tbl)

    # --- MONTANT TOTAL ---
    story.append(Spacer(1, 6*mm))
    mt = Table([[
        Paragraph("Montant de l'appel de fonds", sty(11, True)),
        Paragraph(f"<b>{total_lot:,.2f} €</b>", sty(14, True, 'RIGHT'))
    ]], colWidths=[130*mm, 50*mm])
    mt.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LINEABOVE',(0,0),(-1,0),1.5,colors.black),
        ('TOPPADDING',(0,0),(-1,0),6),
    ]))
    story.append(mt)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

def generate_regularisation_pdf_bytes(syndic, cop_row, annee,
                                       budgets_appel, dep_reel_type,
                                       alur_annuel_reg, nb_appels_reg):
    """Génère le PDF du 5ème appel de régularisation pour un copropriétaire."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from io import BytesIO
    from datetime import date

    JAUNE       = colors.HexColor('#FFD700')
    JAUNE_CLAIR = colors.HexColor('#FFFACD')
    VERT_CLAIR  = colors.HexColor('#E8F5E9')
    ROUGE_CLAIR = colors.HexColor('#FFEBEE')
    BLEU        = colors.HexColor('#4472C4')
    GRIS_CLAIR  = colors.HexColor('#D9D9D9')

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=15*mm)

    def sty(size=9, bold=False, align='LEFT', color=colors.black):
        al = {'LEFT': TA_LEFT, 'RIGHT': TA_RIGHT, 'CENTER': TA_CENTER}[align]
        return ParagraphStyle('s', fontSize=size,
                              fontName='Helvetica-Bold' if bold else 'Helvetica',
                              textColor=color, alignment=al, leading=size * 1.3)

    story = []
    date_str = date.today().strftime('%d/%m/%Y')

    # ── EN-TÊTE ──────────────────────────────────────────────────
    header = Table([[
        [Paragraph("<u><b>5ème Appel de Fonds — Régularisation</b></u>", sty(16, True)),
         Paragraph(f"Exercice {annee}", sty(9)),
         Paragraph(f"Basé sur {nb_appels_reg} appels provisionnels versés", sty(9))],
        [Paragraph(f"A {syndic['ville']}, le {date_str}", sty(9, align='RIGHT')),
         Paragraph(f"<b>{syndic['nom']}</b>", sty(9, True, 'RIGHT')),
         Paragraph(syndic['adresse'], sty(9, align='RIGHT')),
         Paragraph(syndic['cp_ville'], sty(9, align='RIGHT'))]
    ]], colWidths=[100*mm, 80*mm])
    header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(header)
    story.append(Spacer(1, 5*mm))

    # ── BLOC RÉF / DESTINATAIRE ───────────────────────────────────
    nom_cop  = str(cop_row.get('nom', ''))
    ref_cop  = f"0275-{str(cop_row.get('lot','')).zfill(4)}"
    adresse  = str(cop_row.get('adresse', '') or '')
    cp_ville = str(cop_row.get('cp_ville', '') or '')
    login    = str(cop_row.get('login', '') or '')

    ref_tbl = Table([[
        [Paragraph(f"<b>RÉGULARISATION DES CHARGES {annee}</b>", sty(9, True)),
         Paragraph(f"Réf : {ref_cop} / {nom_cop}", sty(9)),
         Paragraph(f"Internet Login : {login}  Mot de Passe :", sty(9))],
        [],
        [Paragraph(f"<b>{nom_cop}</b>", sty(9, True)),
         Paragraph(adresse, sty(9)),
         Paragraph(cp_ville, sty(9))]
    ]], colWidths=[80*mm, 20*mm, 80*mm])
    ref_tbl.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(ref_tbl)
    story.append(Spacer(1, 6*mm))

    # ── TABLEAU PRINCIPAL ─────────────────────────────────────────
    # Colonnes : Désignation | Dép. réelles | Base | Tantièmes | Appels versés | Charges réelles | Différence
    col_widths = [14*mm, 55*mm, 20*mm, 20*mm, 15*mm, 22*mm, 22*mm, 22*mm]
    thead = [['',
        Paragraph('Désignation', sty(8, True, 'CENTER', colors.white)),
        Paragraph('Dép. réelles', sty(8, True, 'CENTER', colors.white)),
        Paragraph('Base', sty(8, True, 'CENTER', colors.white)),
        Paragraph('Tants', sty(8, True, 'CENTER', colors.white)),
        Paragraph('Appels versés', sty(8, True, 'CENTER', colors.white)),
        Paragraph('Charges réelles', sty(8, True, 'CENTER', colors.white)),
        Paragraph('Différence', sty(8, True, 'CENTER', colors.white)),
    ]]

    lot   = str(cop_row.get('lot', ''))
    usage = str(cop_row.get('usage', ''))
    rows  = [[
        Paragraph(f"<b>{lot}</b>", sty(9, True)),
        Paragraph(f"<b>{usage}</b>", sty(9, True)),
        '', '', '', '', '', ''
    ]]

    total_appels   = 0
    total_charges  = 0
    total_dep_reel = 0

    for key, cfg in CHARGES_CONFIG.items():
        tant = float(cop_row.get(cfg['col'], 0) or 0)
        if tant == 0 or cfg['total'] == 0:
            continue
        budget_an  = budgets_appel.get(key, 0)
        dep_reel   = dep_reel_type.get(key, 0)
        appel_cop  = round((tant / cfg['total']) * budget_an, 2)
        charge_cop = round((tant / cfg['total']) * dep_reel, 2)
        diff       = round(charge_cop - appel_cop, 2)

        if appel_cop == 0 and charge_cop == 0:
            continue

        total_appels   += appel_cop
        total_charges  += charge_cop
        total_dep_reel += dep_reel

        rows.append([
            '',
            Paragraph(POSTES_LABELS.get(key, cfg['label']), sty(8)),
            Paragraph(f"{dep_reel:,.2f}", sty(8, align='RIGHT')),
            Paragraph(str(cfg['total']), sty(8, align='CENTER')),
            Paragraph(str(int(tant)), sty(8, align='CENTER')),
            Paragraph(f"{appel_cop:,.2f}", sty(8, align='RIGHT')),
            Paragraph(f"{charge_cop:,.2f}", sty(8, align='RIGHT')),
            Paragraph(f"{diff:+,.2f}", sty(8, align='RIGHT')),
        ])

    # Ligne Alur (informatif)
    tant_gen = float(cop_row.get('tantieme_general', 0) or 0)
    if tant_gen > 0 and alur_annuel_reg > 0:
        alur_cop = round(tant_gen / 10000 * alur_annuel_reg, 2)
        rows.append([
            '',
            Paragraph('FONDS TRAVAUX ALUR (info)', sty(8)),
            Paragraph('—', sty(8, align='CENTER')),
            Paragraph('10000', sty(8, align='CENTER')),
            Paragraph(str(int(tant_gen)), sty(8, align='CENTER')),
            Paragraph(f"{alur_cop:,.2f}", sty(8, align='RIGHT')),
            Paragraph(f"{alur_cop:,.2f}", sty(8, align='RIGHT')),
            Paragraph("0,00", sty(8, align='RIGHT')),
        ])

    # Sous-total charges courantes
    diff_total = round(total_charges - total_appels, 2)
    rows.append([
        '',
        Paragraph('<b>SOUS-TOTAL CHARGES</b>', sty(9, True, 'RIGHT')),
        '', '', '',
        Paragraph(f"<b>{total_appels:,.2f}</b>", sty(9, True, 'RIGHT')),
        Paragraph(f"<b>{total_charges:,.2f}</b>", sty(9, True, 'RIGHT')),
        Paragraph(f"<b>{diff_total:+,.2f}</b>", sty(9, True, 'RIGHT')),
    ])

    # DONT TVA
    dont_tva_appels  = round(total_appels * 20 / 120, 2)
    dont_tva_charges = round(total_charges * 20 / 120, 2)
    rows.append([
        '',
        Paragraph('<b>DONT TVA</b>', sty(9, True, 'RIGHT')),
        '', '', '',
        Paragraph(f"<b>{dont_tva_appels:,.2f}</b>", sty(9, True, 'RIGHT')),
        Paragraph(f"<b>{dont_tva_charges:,.2f}</b>", sty(9, True, 'RIGHT')),
        Paragraph(f"<b>{round(dont_tva_charges - dont_tva_appels, 2):+,.2f}</b>", sty(9, True, 'RIGHT')),
    ])

    table_data = thead + rows
    n = len(table_data)
    n_lot    = 1
    n_ds     = 2
    n_de     = n - 3
    n_alur   = n - 3 if tant_gen > 0 and alur_annuel_reg > 0 else None
    n_stotal = n - 2
    n_tva    = n - 1

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_rules = [
        ('BACKGROUND', (0,0), (-1,0), BLEU),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN',      (0,0), (-1,0), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('BACKGROUND', (0,n_lot), (-1,n_lot), GRIS_CLAIR),
        ('BACKGROUND', (0,n_stotal), (-1,n_stotal), JAUNE),
        ('BACKGROUND', (0,n_tva),    (-1,n_tva),    JAUNE_CLAIR),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#CCCCCC')),
        ('BOX',  (0,0), (-1,-1), 1,   colors.HexColor('#999999')),
        ('ALIGN', (2,1), (2,-1), 'RIGHT'),
        ('ALIGN', (3,1), (3,-1), 'CENTER'),
        ('ALIGN', (4,1), (4,-1), 'CENTER'),
        ('ALIGN', (5,1), (5,-1), 'RIGHT'),
        ('ALIGN', (6,1), (6,-1), 'RIGHT'),
        ('ALIGN', (7,1), (7,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,1), (-1,-1), 3),
        ('BOTTOMPADDING', (0,1), (-1,-1), 3),
        ('LEFTPADDING', (1,0), (1,-1), 4),
    ]
    # Colorer la colonne différence selon positif/négatif par ligne
    for i in range(n_ds, n_stotal):
        bg = colors.white if i % 2 == 0 else colors.HexColor('#F5F5F5')
        style_rules.append(('BACKGROUND', (0,i), (6,i), bg))
    tbl.setStyle(TableStyle(style_rules))
    story.append(tbl)

    # ── MONTANT FINAL ─────────────────────────────────────────────
    story.append(Spacer(1, 6*mm))

    sens_txt = "Montant à appeler" if diff_total >= 0 else "Montant à rembourser"
    couleur_diff = colors.HexColor('#B71C1C') if diff_total >= 0 else colors.HexColor('#1B5E20')
    mt = Table([[
        Paragraph(f"<b>{sens_txt}</b>", sty(11, True)),
        Paragraph(f"<b>{abs(diff_total):,.2f} €</b>",
                  sty(14, True, 'RIGHT', couleur_diff))
    ]], colWidths=[120*mm, 60*mm])
    mt.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEABOVE', (0,0), (-1,0), 1.5, colors.black),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,0), (-1,0), VERT_CLAIR if diff_total < 0 else ROUGE_CLAIR),
    ]))
    story.append(mt)

    # ── NOTE BAS DE PAGE ──────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    note = (f"Régularisation basée sur {nb_appels_reg} appel(s) provisionnel(s) versé(s) — "
            f"Exercice {annee} — Émis le {date_str}")
    story.append(Paragraph(note, sty(7, color=colors.grey)))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


CHARGES_CONFIG = {
    'general':    {'col': 'tantieme_general',        'total': 10000, 'label': 'Charges générales',        'emoji': '🏢', 'classes': ['1A','1B','7']},
    'ascenseurs': {'col': 'tantiemes_ascenseur',     'total': 1000,  'label': 'Ascenseurs',               'emoji': '🛗', 'classes': ['5']},
    'rdc_ssols':  {'col': 'tantiemes_special_rdc_ss','total': 928,   'label': 'Charges spéc. RDC S/Sols', 'emoji': '🅿️', 'classes': ['2']},
    'ssols_elec': {'col': 'tantieme_ssols',          'total': 20,    'label': 'Charges spéc. S/Sols',     'emoji': '⬇️', 'classes': ['3']},
    'garages':    {'col': 'tantieme_garages',        'total': 28,    'label': 'Garages / Parkings',       'emoji': '🔑', 'classes': ['4']},
    'ssols':      {'col': 'tantieme_monte_voitures', 'total': 20,    'label': 'Monte-voitures',           'emoji': '🚗', 'classes': ['6']},
}

def prepare_copro(copro_df):
    """Convertit toutes les colonnes tantièmes en numérique."""
    for col in ['tantieme_general','tantiemes_ascenseur','tantiemes_special_rdc_ss',
                  'tantieme_rdc_ssols','tantieme_ssols','tantieme_garages',
                  'tantieme_ascenseurs','tantieme_monte_voitures','tantieme']:
        if col in copro_df.columns:
            copro_df[col] = pd.to_numeric(copro_df[col], errors='coerce').fillna(0)
    # Fallback si les colonnes spécifiques ne sont pas remplies
    if 'tantieme_general' not in copro_df.columns or copro_df['tantieme_general'].sum() == 0:
        if 'tantieme' in copro_df.columns:
            copro_df['tantieme_general'] = copro_df['tantieme']
    return copro_df

def calculer_appels(copro_df, montants_par_type):
    """Calcule la part de chaque copropriétaire selon les montants par type de charge."""
    rows = []
    for _, cop in copro_df.iterrows():
        total_annuel = 0
        detail = {}
        for key, cfg in CHARGES_CONFIG.items():
            col = cfg['col']
            tant = float(cop.get(col, 0) or 0)
            montant = montants_par_type.get(key, 0)
            part = (tant / cfg['total'] * montant) if cfg['total'] > 0 and tant > 0 else 0
            detail[key] = round(part, 2)
            total_annuel += part
        row = {
            'Lot': cop.get('lot',''), 'Copropriétaire': cop.get('nom',''),
            'Étage': cop.get('etage',''), 'Usage': cop.get('usage',''),
            '_tantieme_general': float(cop.get('tantieme_general', 0) or 0),  # pour calcul Alur
        }
        row.update({f"{CHARGES_CONFIG[k]['emoji']} {CHARGES_CONFIG[k]['label']}": v for k, v in detail.items()})
        row['💰 TOTAL Annuel (€)'] = round(total_annuel, 2)
        rows.append(row)
    return pd.DataFrame(rows)

# ==================== MENU ====================
st.sidebar.image("https://img.icons8.com/color/96/000000/office-building.png", width=100)
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Choisir une section", [
    "📊 Tableau de Bord", "💰 Budget", "📝 Dépenses",
    "👥 Copropriétaires", "🔄 Répartition", "🏛️ Loi Alur", "📈 Analyses", "📋 Plan Comptable",
    "🏛 AG — Assemblée Générale", "📒 Grand Livre", "📑 Contrats Fournisseurs",
    "📬 Communications", "🏠 Locataires"
])

# ==================== TABLEAU DE BORD ====================
if menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)
    budget_df = get_budget()
    depenses_df = get_depenses()

    if not budget_df.empty and not depenses_df.empty:
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df['annee'] = depenses_df['date'].dt.year
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            annee_filter = st.selectbox("📅 Année", sorted(depenses_df['annee'].unique(), reverse=True), key="tdb_annee")
        with col2:
            classes_dispo = ['Toutes'] + sorted([str(c) for c in depenses_df['classe'].dropna().unique()]) if 'classe' in depenses_df.columns else ['Toutes']
            classe_filter = st.selectbox("🏷️ Classe", classes_dispo, key="tdb_classe")
        with col3:
            comptes_dispo = ['Tous'] + sorted(depenses_df['compte'].dropna().unique().tolist())
            compte_filter = st.selectbox("🔢 Compte", comptes_dispo, key="tdb_compte")
        with col4:
            alur_taux_tdb = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_tdb")

        dep_f = depenses_df[depenses_df['annee'] == annee_filter].copy()
        if classe_filter != 'Toutes' and 'classe' in dep_f.columns:
            dep_f = dep_f[dep_f['classe'] == classe_filter]
        if compte_filter != 'Tous':
            dep_f = dep_f[dep_f['compte'] == compte_filter]

        bud_f = budget_df[budget_df['annee'] == annee_filter].copy()
        if classe_filter != 'Toutes' and 'classe' in bud_f.columns:
            bud_f = bud_f[bud_f['classe'] == classe_filter]
        if compte_filter != 'Tous':
            bud_f = bud_f[bud_f['compte'] == compte_filter]

        # Alur toujours calculé sur le budget TOTAL de l'année (pas filtré)
        bud_total_annee_tdb = float(budget_df[budget_df['annee'] == annee_filter]['montant_budget'].sum())
        alur_tdb = round(bud_total_annee_tdb * alur_taux_tdb / 100, 2)

        total_budget = float(bud_f['montant_budget'].sum())
        total_dep = float(dep_f['montant_du'].sum())
        total_a_appeler = bud_total_annee_tdb + alur_tdb

        # Travaux votés : montant des dépenses affectées (diminution des charges courantes)
        tv_ids_tdb = get_travaux_votes_depense_ids()
        dep_tv_tdb = dep_f[dep_f['id'].isin(tv_ids_tdb)] if not dep_f.empty and tv_ids_tdb else pd.DataFrame()
        montant_tv_tdb = float(dep_tv_tdb['montant_du'].sum()) if not dep_tv_tdb.empty else 0

        # Dépenses courantes nettes = total − travaux votés
        total_dep_net = total_dep - montant_tv_tdb

        ecart = total_a_appeler - total_dep_net
        pct = (total_dep_net / total_a_appeler * 100) if total_a_appeler > 0 else 0

        st.divider()
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        c1.metric("Budget charges", f"{bud_total_annee_tdb:,.0f} €")
        c2.metric(f"🏛️ Alur ({alur_taux_tdb:.0f}%)", f"{alur_tdb:,.0f} €")
        c3.metric("💰 Total à appeler", f"{total_a_appeler:,.0f} €")
        c4.metric("Dépenses réelles", f"{total_dep:,.2f} €")
        if montant_tv_tdb > 0:
            c5.metric("🏗️ — Travaux votés", f"-{montant_tv_tdb:,.2f} €",
                help="Dépenses affectées aux travaux votés en AG — déduites des charges courantes")
            c6.metric("Dépenses nettes", f"{total_dep_net:,.2f} €",
                help="Dépenses réelles − Travaux votés")
            c7.metric("Écart", f"{ecart:,.2f} €",
                delta_color="normal" if ecart >= 0 else "inverse",
                help="Total à appeler − Dépenses nettes")
        else:
            c5.metric("Écart", f"{ecart:,.2f} €",
                delta_color="normal" if ecart >= 0 else "inverse",
                help="Total à appeler − Dépenses réelles")
            c6.metric("% Réalisé", f"{pct:.1f}%")

        # Bandeau info
        info_parts = [f"🏛️ **Loi Alur** — {alur_tdb:,.0f} € /an "
                      f"({alur_taux_tdb:.0f}% × {bud_total_annee_tdb:,.0f} €) "
                      f"— soit **{alur_tdb/4:,.2f} €** par appel trimestriel"]
        if montant_tv_tdb > 0:
            info_parts.append(f"🏗️ **Travaux votés** — {montant_tv_tdb:,.2f} € déduits des charges courantes")
        st.info("   |   ".join(info_parts))
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Budget + Alur vs Dépenses par Classe")
            if 'classe' in bud_f.columns and 'classe' in dep_f.columns:
                bud_cl = bud_f.groupby('classe')['montant_budget'].sum().reset_index()
                # Ajouter Alur comme classe distincte
                alur_bar = pd.DataFrame([{'classe': f'Alur ({alur_taux_tdb:.0f}%)', 'montant_budget': alur_tdb}])
                bud_cl_total = pd.concat([bud_cl, alur_bar], ignore_index=True)
                dep_cl = dep_f.groupby('classe')['montant_du'].sum().reset_index()
                comp = bud_cl_total.merge(dep_cl, on='classe', how='left').fillna(0)
                comp.columns = ['Classe', 'Budget', 'Dépenses']
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Budget + Alur', x=comp['Classe'], y=comp['Budget'], marker_color='lightblue'))
                fig.add_trace(go.Bar(name='Dépenses réelles', x=comp['Classe'], y=comp['Dépenses'], marker_color='salmon'))
                fig.update_layout(barmode='group', height=400)
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Répartition Budget + Alur")
            if 'classe' in bud_f.columns and not bud_f.empty:
                bud_cl = bud_f.groupby('classe')['montant_budget'].sum().reset_index()
                bud_cl_pie = pd.concat([bud_cl, pd.DataFrame([{
                    'classe': f'Alur ({alur_taux_tdb:.0f}%)', 'montant_budget': alur_tdb
                }])], ignore_index=True)
                fig = px.pie(bud_cl_pie, values='montant_budget', names='classe',
                    title=f'Distribution budget + Alur {annee_filter}')
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Évolution Mensuelle — {annee_filter}")
        if not dep_f.empty:
            dep_f['mois'] = dep_f['date'].dt.to_period('M').astype(str)
            ev = dep_f.groupby('mois')['montant_du'].sum().reset_index()
            # Ajouter ligne budget mensuel moyen
            bud_mensuel = total_a_appeler / 12
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ev['mois'], y=ev['montant_du'], mode='lines+markers',
                name='Dépenses réelles', line=dict(color='#1f77b4', width=3)))
            fig.add_hline(y=bud_mensuel, line_dash='dash', line_color='orange',
                annotation_text=f"Moy. budget+Alur/mois ({bud_mensuel:,.0f} €)")
            fig.update_layout(xaxis_title='Mois', yaxis_title='Montant (€)')
            st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Top 10 Dépenses — {annee_filter}")
        if not dep_f.empty:
            top = dep_f.nlargest(10, 'montant_du')[['date','fournisseur','montant_du','commentaire']].copy()
            top['date'] = top['date'].dt.strftime('%d/%m/%Y')
            st.dataframe(top, use_container_width=True, hide_index=True,
                column_config={"montant_du": st.column_config.NumberColumn("Montant (€)", format="%,.2f")})
    else:
        st.warning("⚠️ Données insuffisantes")

# ==================== BUDGET ====================
elif menu == "💰 Budget":
    st.markdown("<h1 class='main-header'>💰 Gestion du Budget</h1>", unsafe_allow_html=True)
    budget_df = get_budget()

    if not budget_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            annees = sorted(budget_df['annee'].unique(), reverse=True)
            annee_filter = st.selectbox("📅 Année", annees, key="budget_annee")
        with col2:
            classe_filter = st.multiselect("🏷️ Classe", options=sorted(budget_df['classe'].unique()))
        with col3:
            famille_filter = st.multiselect("📂 Famille", options=sorted(budget_df['famille'].unique()))
        with col4:
            alur_taux_bud = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_bud",
                help="Minimum légal = 5% du budget voté en AG (loi Alur art. 14-2)")

        filt = budget_df[budget_df['annee'] == annee_filter].copy()
        if classe_filter: filt = filt[filt['classe'].isin(classe_filter)]
        if famille_filter: filt = filt[filt['famille'].isin(famille_filter)]
        bud_total_annee = float(budget_df[budget_df['annee'] == annee_filter]['montant_budget'].sum())
        alur_annuel_bud = round(bud_total_annee * alur_taux_bud / 100, 2)

        st.divider()
        bud_prec = float(budget_df[budget_df['annee'] == annee_filter - 1]['montant_budget'].sum())
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Postes budgétaires", len(filt))
        c2.metric("Budget charges", f"{bud_total_annee:,.0f} €")
        c3.metric(f"🏛️ Alur ({alur_taux_bud:.0f}%)", f"{alur_annuel_bud:,.0f} €",
            help=f"{alur_taux_bud}% × {bud_total_annee:,.0f} € = fonds de travaux obligatoire")
        c4.metric("💰 TOTAL à appeler", f"{bud_total_annee + alur_annuel_bud:,.0f} €")
        if bud_prec > 0:
            c5.metric("vs N-1", f"{(bud_total_annee - bud_prec) / bud_prec * 100:+.1f}%",
                delta=f"{bud_total_annee - bud_prec:+,.0f} €")
        else:
            c5.metric("vs N-1", "N/A")

        # Bloc Alur détaillé
        st.info(f"🏛️ **Loi Alur** — Fonds de travaux : **{alur_annuel_bud:,.0f} €/an** "
                f"({alur_taux_bud:.0f}% × {bud_total_annee:,.0f} €) "
                f"— soit **{alur_annuel_bud/4:,.2f} €/trimestre** par appel de fonds")
        st.divider()

        tab1, tab2, tab3 = st.tabs(["📋 Consulter", "✏️ Modifier / Ajouter / Supprimer", "➕ Créer Budget Année"])

        with tab1:
            st.subheader(f"Budget {annee_filter} — {len(filt)} postes")

            # Tableau avec ligne Alur et total — utilise alur_annuel_bud/bud_total_annee déjà calculés
            filt_display = filt[['compte','libelle_compte','montant_budget','classe','famille']].sort_values('compte').copy()
            filt_display = pd.concat([filt_display, pd.DataFrame([
                {'compte': 'ALUR', 'libelle_compte': f'🏛️ FONDS DE TRAVAUX — Loi Alur ({alur_taux_bud:.0f}%)',
                 'montant_budget': alur_annuel_bud, 'classe': '—', 'famille': '—'},
                {'compte': 'TOTAL', 'libelle_compte': '💰 TOTAL BUDGET + ALUR',
                 'montant_budget': bud_total_annee + alur_annuel_bud, 'classe': '—', 'famille': '—'}
            ])], ignore_index=True)

            st.dataframe(filt_display, use_container_width=True, hide_index=True,
                column_config={
                    "compte": st.column_config.TextColumn("Compte"),
                    "libelle_compte": st.column_config.TextColumn("Libellé"),
                    "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%,.0f"),
                    "classe": st.column_config.TextColumn("Classe"),
                    "famille": st.column_config.TextColumn("Famille"),
                })

            col1, col2 = st.columns(2)
            with col1:
                bud_cl = filt.groupby('classe')['montant_budget'].sum().reset_index()
                bud_cl_graph = pd.concat([bud_cl, pd.DataFrame([
                    {'classe': f'Alur ({alur_taux_bud:.0f}%)', 'montant_budget': alur_annuel_bud}
                ])], ignore_index=True)
                fig = px.bar(bud_cl_graph, x='classe', y='montant_budget',
                    title=f"Budget {annee_filter} par Classe + Alur",
                    labels={'montant_budget':'Budget (€)','classe':'Classe'}, color='classe')
                fig.update_traces(texttemplate='%{y:,.0f}€', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.pie(bud_cl_graph, values='montant_budget', names='classe',
                    title=f"Répartition Budget + Alur {annee_filter}")
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

            st.download_button("📥 Exporter CSV (avec Alur)",
                filt_display.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig'),
                f"budget_{annee_filter}.csv", "text/csv")

        with tab2:
            subtab1, subtab2, subtab3 = st.tabs(["✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer"])
            with subtab1:
                bud_edit_df = filt[['id','compte','libelle_compte','montant_budget','classe','famille']].copy()
                bud_edit_df['compte'] = bud_edit_df['compte'].astype(str).fillna('')
                bud_edit_df['libelle_compte'] = bud_edit_df['libelle_compte'].astype(str).fillna('')
                bud_edit_df['montant_budget'] = pd.to_numeric(bud_edit_df['montant_budget'], errors='coerce').fillna(0.0)
                bud_edit_df['classe'] = bud_edit_df['classe'].astype(str).fillna('')
                bud_edit_df['famille'] = bud_edit_df['famille'].astype(str).fillna('')
                edited = st.data_editor(
                    bud_edit_df,
                    use_container_width=True, hide_index=True, disabled=['id'],
                    column_config={
                        "compte": st.column_config.TextColumn("Compte"),
                        "libelle_compte": st.column_config.TextColumn("Libellé"),
                        "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%.0f", min_value=0),
                        "classe": st.column_config.SelectboxColumn("Classe", options=['1A','1B','2','3','4','5','6','7']),
                        "famille": st.column_config.TextColumn("Famille"),
                    }, key="budget_editor"
                )
                if st.button("💾 Enregistrer", type="primary", key="save_bud"):
                    try:
                        mods = 0
                        for _, row in edited.iterrows():
                            orig = filt[filt['id'] == row['id']]
                            if orig.empty: continue
                            o = orig.iloc[0]; updates = {}
                            if str(row['compte']) != str(o['compte']): updates['compte'] = str(row['compte'])
                            if str(row['libelle_compte']) != str(o['libelle_compte']): updates['libelle_compte'] = str(row['libelle_compte'])
                            if float(row['montant_budget']) != float(o['montant_budget']): updates['montant_budget'] = int(row['montant_budget'])
                            if str(row['classe']) != str(o['classe']): updates['classe'] = str(row['classe'])
                            if str(row['famille']) != str(o['famille']): updates['famille'] = str(row['famille'])
                            if updates:
                                supabase.table('budget').update(updates).eq('id', int(row['id'])).execute()
                                mods += 1
                        st.success(f"✅ {mods} ligne(s) mise(s) à jour!") if mods > 0 else st.info("Aucune modification")
                        if mods > 0: st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

            with subtab2:
                plan_df = get_plan_comptable()
                new_compte = st.text_input("Numéro de compte *", key="new_compte_in")
                compte_info = plan_df[plan_df['compte'].astype(str) == str(new_compte)] if new_compte and not plan_df.empty else pd.DataFrame()
                if not compte_info.empty:
                    st.success(f"✅ {compte_info.iloc[0]['libelle_compte']}")
                    def_lib = compte_info.iloc[0]['libelle_compte']
                    def_cl = compte_info.iloc[0]['classe']
                    def_fam = str(compte_info.iloc[0]['famille'])
                elif new_compte:
                    st.warning("⚠️ Compte non trouvé dans le plan comptable")
                    def_lib = ""; def_cl = "1A"; def_fam = ""
                else:
                    def_lib = ""; def_cl = "1A"; def_fam = ""

                col1, col2 = st.columns(2)
                with col1:
                    new_lib = st.text_input("Libellé *", value=def_lib, key="new_lib_in")
                    new_montant = st.number_input("Montant (€) *", min_value=0, step=100, key="new_montant_in")
                with col2:
                    new_classe = st.selectbox("Classe *", ['1A','1B','2','3','4','5','6','7'],
                        index=['1A','1B','2','3','4','5','6','7'].index(def_cl) if def_cl in ['1A','1B','2','3','4','5','6','7'] else 0,
                        key="new_classe_in")
                    new_famille = st.text_input("Famille *", value=def_fam, key="new_fam_in")

                if st.button("✨ Ajouter", type="primary", key="add_bud"):
                    if new_compte and new_lib and new_famille:
                        try:
                            supabase.table('budget').insert({
                                'compte': new_compte, 'libelle_compte': new_lib,
                                'montant_budget': int(new_montant), 'annee': int(annee_filter),
                                'classe': new_classe, 'famille': new_famille
                            }).execute()
                            st.success("✅ Compte ajouté!"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")
                    else:
                        st.error("❌ Remplissez tous les champs obligatoires")

            with subtab3:
                st.warning("⚠️ La suppression est définitive.")
                ids_del = st.multiselect("Sélectionner les postes à supprimer", options=filt['id'].tolist(),
                    format_func=lambda x: f"{filt[filt['id']==x]['compte'].values[0]} — {filt[filt['id']==x]['libelle_compte'].values[0]}")
                if ids_del:
                    if st.button("🗑️ Confirmer la suppression", type="secondary"):
                        for i in ids_del: supabase.table('budget').delete().eq('id', i).execute()
                        st.success(f"✅ {len(ids_del)} poste(s) supprimé(s)"); st.rerun()

        with tab3:
            st.subheader("Créer un budget pour une nouvelle année")
            c1, c2 = st.columns(2)
            with c1:
                nouvelle_annee = st.number_input("📅 Nouvelle année", min_value=2020, max_value=2050, value=annee_filter+1, step=1)
            with c2:
                annee_src = st.selectbox("Copier depuis", annees)
            src = budget_df[budget_df['annee'] == annee_src].copy()
            ajust = st.radio("Ajustement", ["Aucun", "Pourcentage"])
            if ajust == "Pourcentage":
                coeff = st.number_input("% +/-", min_value=-50.0, max_value=100.0, value=3.0, step=0.5) / 100
                src['nouveau_montant'] = (src['montant_budget'] * (1+coeff)).round(0).astype(int)
            else:
                src['nouveau_montant'] = src['montant_budget']
            st.metric(f"Budget {nouvelle_annee}", f"{src['nouveau_montant'].sum():,.0f} €")
            existe = not budget_df[budget_df['annee'] == nouvelle_annee].empty
            if existe:
                st.warning(f"⚠️ Budget {nouvelle_annee} existe déjà.")
            else:
                if st.button(f"✨ Créer le budget {nouvelle_annee}", type="primary"):
                    try:
                        postes = [{'compte': r['compte'], 'libelle_compte': r['libelle_compte'],
                                   'montant_budget': int(r['nouveau_montant']), 'annee': int(nouvelle_annee),
                                   'classe': r['classe'], 'famille': r['famille']} for _, r in src.iterrows()]
                        for i in range(0, len(postes), 50):
                            supabase.table('budget').insert(postes[i:i+50]).execute()
                        st.success(f"✅ Budget {nouvelle_annee} créé ({len(postes)} postes)!"); st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

# ==================== DÉPENSES ====================
elif menu == "📝 Dépenses":
    st.markdown("<h1 class='main-header'>📝 Gestion des Dépenses</h1>", unsafe_allow_html=True)
    depenses_df = get_depenses()
    budget_df = get_budget()

    if not depenses_df.empty:
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df['annee'] = depenses_df['date'].dt.year
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')

        if not budget_df.empty:
            bud_uniq = budget_df.drop_duplicates(subset=['compte'], keep='first')[['compte','libelle_compte','classe','famille']]
            depenses_df = depenses_df.merge(bud_uniq, on='compte', how='left', suffixes=('','_bud'))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            annee_dep = st.selectbox("📅 Année", sorted(depenses_df['annee'].unique(), reverse=True), key="dep_annee")
        with col2:
            cpt_filter = st.multiselect("🔢 Compte", options=sorted(depenses_df['compte'].dropna().unique()))
        with col3:
            cl_filter = st.multiselect("🏷️ Classe", options=sorted([c for c in depenses_df['classe'].dropna().unique() if c]))
        with col4:
            four_filter = st.multiselect("🏢 Fournisseur", options=sorted(depenses_df['fournisseur'].dropna().unique()))

        dep_f = depenses_df[depenses_df['annee'] == annee_dep].copy()
        if cpt_filter: dep_f = dep_f[dep_f['compte'].isin(cpt_filter)]
        if cl_filter: dep_f = dep_f[dep_f['classe'].isin(cl_filter)]
        if four_filter: dep_f = dep_f[dep_f['fournisseur'].isin(four_filter)]

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        total_dep = dep_f['montant_du'].sum()
        bud_tot = budget_df[budget_df['annee'] == annee_dep]['montant_budget'].sum() if not budget_df.empty and 'annee' in budget_df.columns else 0
        c1.metric("Nb dépenses", len(dep_f))
        c2.metric("Total", f"{total_dep:,.2f} €")
        c3.metric("Moyenne", f"{dep_f['montant_du'].mean():,.2f} €" if len(dep_f) > 0 else "0 €")
        if bud_tot > 0:
            c4.metric("Réalisé vs Budget", f"{total_dep/bud_tot*100:.1f}%", delta=f"{total_dep-bud_tot:,.0f} €")
        else:
            c4.metric("Réalisé vs Budget", "N/A")
        st.divider()

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 Consulter", "✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer", "🏗️ Travaux Votés", "📎 Factures"])

        with tab1:
            if dep_f.empty:
                st.info("Aucune dépense pour cette période.")
            else:
                dep_show = dep_f.copy().sort_values('date', ascending=False)
                dep_show['montant_du'] = pd.to_numeric(dep_show['montant_du'], errors='coerce').fillna(0)
                has_facture_col = 'facture_path' in dep_show.columns

                # Barre de contrôle
                col_vue1, col_vue2 = st.columns([3, 1])
                with col_vue1:
                    vue_mode = st.radio("Affichage", ["📋 Tableau", "📎 Vis-à-vis factures"],
                        horizontal=True, key="dep_vue_mode")
                with col_vue2:
                    st.download_button("📥 CSV",
                        dep_f.to_csv(index=False).encode('utf-8'),
                        f"depenses_{annee_dep}.csv", "text/csv",
                        use_container_width=True)

                # ── MODE TABLEAU ───────────────────────────────────
                if vue_mode == "📋 Tableau":
                    disp = dep_show[['date','compte','libelle_compte','fournisseur','montant_du','classe','commentaire']].copy()
                    disp['date'] = disp['date'].dt.strftime('%d/%m/%Y')
                    if has_facture_col:
                        disp['📎'] = dep_show['facture_path'].apply(
                            lambda x: '✅' if x and str(x) not in ('','None','nan') else '—')
                    st.dataframe(disp, use_container_width=True, hide_index=True,
                        column_config={"montant_du": st.column_config.NumberColumn("Montant (€)", format="%,.2f")})

                # ── MODE VIS-À-VIS FACTURES ────────────────────────
                else:
                    # Filtres
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        fac_filtre = st.radio("Filtrer", ["Toutes", "✅ Avec facture", "❌ Sans facture"],
                            horizontal=True, key="fac_filtre_tab1")
                    with col_f2:
                        fac_search2 = st.text_input("🔍 Fournisseur", key="fac_search_tab1")

                    dep_vis = dep_show.copy()
                    if has_facture_col:
                        has_fac_mask = dep_vis['facture_path'].apply(
                            lambda x: bool(x and str(x) not in ('', 'None', 'nan')))
                        if fac_filtre == "✅ Avec facture":
                            dep_vis = dep_vis[has_fac_mask]
                        elif fac_filtre == "❌ Sans facture":
                            dep_vis = dep_vis[~has_fac_mask]
                    if fac_search2:
                        dep_vis = dep_vis[dep_vis['fournisseur'].astype(str).str.contains(
                            fac_search2, case=False, na=False)]

                    # Métriques
                    if has_facture_col:
                        nb_avec = dep_show['facture_path'].apply(
                            lambda x: bool(x and str(x) not in ('', 'None', 'nan'))).sum()
                        mc1, mc2, mc3 = st.columns(3)
                        mc1.metric("Total dépenses", len(dep_show))
                        mc2.metric("✅ Avec facture", int(nb_avec))
                        mc3.metric("❌ Sans facture", len(dep_show) - int(nb_avec))
                        st.divider()

                    # Ligne par ligne en vis-à-vis
                    for _, row in dep_vis.iterrows():
                        dep_id = int(row['id'])
                        fp = row.get('facture_path', '') if has_facture_col else ''
                        a_facture = bool(fp and str(fp) not in ('', 'None', 'nan'))
                        badge = "✅" if a_facture else "❌"
                        date_fmt = row['date'].strftime('%d/%m/%Y') if hasattr(row['date'], 'strftime') else str(row['date'])

                        with st.expander(
                            f"{badge}  {date_fmt}  ·  {row.get('fournisseur','')}  ·  "
                            f"{row['montant_du']:,.2f} €  ·  {str(row.get('libelle_compte',''))[:40]}",
                            expanded=False
                        ):
                            col_dep, col_fac = st.columns([1, 2])

                            # ── Infos dépense + upload ──────────────
                            with col_dep:
                                st.markdown("**📄 Dépense**")
                                st.markdown(f"""
| | |
|---|---|
| **Date** | {date_fmt} |
| **Compte** | {row.get('compte','')} |
| **Libellé** | {str(row.get('libelle_compte',''))[:45]} |
| **Fournisseur** | {row.get('fournisseur','')} |
| **Montant** | **{row['montant_du']:,.2f} €** |
| **Classe** | {row.get('classe','')} |
| **Commentaire** | {row.get('commentaire','') or '—'} |
""")
                                st.markdown("---")
                                uploaded = st.file_uploader(
                                    "📤 Uploader la facture",
                                    type=['pdf','png','jpg','jpeg','webp'],
                                    key=f"upload_inline_{dep_id}",
                                    help="PDF ou image (JPG, PNG)"
                                )
                                if uploaded:
                                    if st.button("💾 Enregistrer la facture",
                                                 key=f"save_fac_{dep_id}",
                                                 use_container_width=True, type="primary"):
                                        try:
                                            upload_facture(dep_id, uploaded.getvalue(), uploaded.name)
                                            st.success("✅ Facture enregistrée.")
                                            st.cache_data.clear(); st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ {e}")
                                if a_facture:
                                    if st.button("🗑️ Supprimer la facture",
                                                 key=f"del_fac_{dep_id}",
                                                 use_container_width=True):
                                        try:
                                            delete_facture(dep_id, str(fp))
                                            st.success("✅ Supprimée.")
                                            st.cache_data.clear(); st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ {e}")

                            # ── Aperçu facture ──────────────────────
                            with col_fac:
                                st.markdown("**🧾 Facture**")
                                if a_facture:
                                    afficher_facture(str(fp), height=520)
                                else:
                                    st.markdown(
                                        "<div style='height:200px;border:2px dashed #555;"
                                        "border-radius:8px;display:flex;align-items:center;"
                                        "justify-content:center;color:#888;font-size:0.95em;'>"
                                        "📂 Aucune facture — uploadez-en une à gauche"
                                        "</div>",
                                        unsafe_allow_html=True)

        with tab2:
            dep_edit_df = dep_f[['id','date','compte','fournisseur','montant_du','commentaire']].copy()
            dep_edit_df['compte'] = dep_edit_df['compte'].astype(str).fillna('')
            dep_edit_df['fournisseur'] = dep_edit_df['fournisseur'].astype(str).fillna('')
            dep_edit_df['commentaire'] = dep_edit_df['commentaire'].astype(str).fillna('')
            dep_edit_df['montant_du'] = pd.to_numeric(dep_edit_df['montant_du'], errors='coerce').fillna(0.0)
            edited_dep = st.data_editor(
                dep_edit_df,
                use_container_width=True, hide_index=True, disabled=['id'],
                column_config={
                    "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "compte": st.column_config.TextColumn("Compte"),
                    "fournisseur": st.column_config.TextColumn("Fournisseur"),
                    "montant_du": st.column_config.NumberColumn("Montant (€)", format="%.2f"),
                    "commentaire": st.column_config.TextColumn("Commentaire"),
                }, key="dep_editor"
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Enregistrer", type="primary", key="save_dep"):
                    try:
                        mods = 0
                        for _, row in edited_dep.iterrows():
                            orig = dep_f[dep_f['id'] == row['id']]
                            if orig.empty: continue
                            o = orig.iloc[0]; updates = {}
                            date_new = pd.Timestamp(row['date']).strftime('%Y-%m-%d')
                            if date_new != o['date'].strftime('%Y-%m-%d'): updates['date'] = date_new
                            if str(row['compte']) != str(o['compte']): updates['compte'] = str(row['compte'])
                            if str(row['fournisseur']) != str(o['fournisseur']): updates['fournisseur'] = str(row['fournisseur'])
                            if float(row['montant_du']) != float(o['montant_du']): updates['montant_du'] = float(row['montant_du'])
                            if updates:
                                supabase.table('depenses').update(updates).eq('id', int(row['id'])).execute(); mods += 1
                        st.success(f"✅ {mods} ligne(s) mise(s) à jour!") if mods > 0 else st.info("Aucune modification")
                        if mods > 0: st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
            with col2:
                if st.button("🔄 Annuler", key="cancel_dep"): st.rerun()

        with tab3:
            new_cpt = st.text_input("Numéro de compte *", key="new_dep_cpt")
            cpt_bud = budget_df[budget_df['compte'].astype(str) == str(new_cpt)] if new_cpt and not budget_df.empty else pd.DataFrame()
            if not cpt_bud.empty:
                st.success(f"✅ {cpt_bud.iloc[0]['libelle_compte']} — Classe {cpt_bud.iloc[0]['classe']}")
                auto_classe = str(cpt_bud.iloc[0]['classe'])
                auto_famille = str(cpt_bud.iloc[0]['famille'])
            else:
                auto_classe = None; auto_famille = None
                if new_cpt: st.warning("⚠️ Compte non trouvé dans le budget")
            with st.form("form_dep"):
                c1, c2 = st.columns(2)
                with c1:
                    dep_date = st.date_input("Date *", value=datetime.now())
                    dep_four = st.text_input("Fournisseur *")
                with c2:
                    dep_mont = st.number_input("Montant (€) *", step=0.01, format="%.2f")
                    dep_comm = st.text_area("Commentaire")
                if st.form_submit_button("✨ Ajouter la dépense", type="primary", use_container_width=True):
                    if new_cpt and auto_classe and dep_four and dep_mont != 0:
                        try:
                            supabase.table('depenses').insert({
                                'date': dep_date.strftime('%Y-%m-%d'), 'compte': new_cpt,
                                'fournisseur': dep_four.strip(), 'montant_du': float(dep_mont),
                                'classe': auto_classe, 'famille': auto_famille,
                                'commentaire': dep_comm.strip() if dep_comm else None
                            }).execute()
                            st.success("✅ Dépense ajoutée!"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")
                    else:
                        st.error("❌ Remplissez tous les champs obligatoires (compte valide, fournisseur, montant ≠ 0)")

        with tab4:
            st.warning("⚠️ La suppression est définitive.")
            ids_del = st.multiselect("Sélectionner les dépenses",
                options=dep_f['id'].tolist(),
                format_func=lambda x: f"ID {x} — {dep_f[dep_f['id']==x]['fournisseur'].values[0]} — {dep_f[dep_f['id']==x]['montant_du'].values[0]:.2f} €")
            if ids_del:
                if st.button("🗑️ Confirmer la suppression", type="secondary"):
                    for i in ids_del: supabase.table('depenses').delete().eq('id', i).execute()
                    st.success(f"✅ {len(ids_del)} dépense(s) supprimée(s)"); st.rerun()
        with tab5:
            st.subheader("🏗️ Travaux Votés en Assemblée Générale")
            st.info("""
            Les **travaux votés en AG** sont financés par appel de fonds spécifique et ne font pas partie
            des charges courantes. Les factures affectées ici sont **déduites des dépenses courantes**
            et n'entrent pas dans le calcul du 5ème appel de charges.
            """)

            tv_df = get_travaux_votes()
            tv_dep_ids = get_travaux_votes_depense_ids()

            # Métriques
            if not tv_df.empty:
                tv_df['date'] = pd.to_datetime(tv_df['date'])
                tv_df['montant'] = pd.to_numeric(tv_df['montant'], errors='coerce').fillna(0)
                tv_df['commentaire'] = tv_df['commentaire'].fillna('').astype(str).replace('None','')

            total_tv = tv_df['montant'].sum() if not tv_df.empty else 0
            nb_tv = len(tv_df) if not tv_df.empty else 0
            nb_dep_transferees = len([x for x in tv_dep_ids if x])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Nb travaux", nb_tv)
            c2.metric("Montant total", f"{total_tv:,.2f} €")
            c3.metric("Factures transférées", nb_dep_transferees)
            # Nb dépenses courantes de l'année filtrées par les transferts
            dep_tv_annee = dep_f[dep_f['id'].isin(tv_dep_ids)]
            c4.metric("Déduit des charges", f"{dep_tv_annee['montant_du'].sum():,.2f} €",
                help="Montant des factures de cette année transférées en travaux votés")

            st.divider()

            subtab1, subtab1b, subtab2, subtab3, subtab4 = st.tabs([
                "📋 Liste", "✏️ Modifier", "➕ Nouveau chantier", "🔗 Transférer factures", "🗑️ Gérer"
            ])

            # ---- LISTE ----
            with subtab1:
                if tv_df.empty:
                    st.info("💡 Aucun travail voté enregistré.")
                else:
                    # Grouper par objet/chantier si la colonne existe
                    disp_tv = tv_df.copy().sort_values('date', ascending=False)
                    disp_tv['date_fmt'] = disp_tv['date'].dt.strftime('%d/%m/%Y')
                    disp_tv['Source'] = disp_tv['depense_id'].apply(
                        lambda x: '🔗 Transférée' if pd.notna(x) and x else '✏️ Saisie manuelle')

                    cols_show = ['date_fmt','objet','fournisseur','montant','commentaire','Source']
                    cols_show = [c for c in cols_show if c in disp_tv.columns]
                    st.dataframe(
                        disp_tv[cols_show].rename(columns={
                            'date_fmt':'Date','objet':'Objet / Chantier',
                            'fournisseur':'Fournisseur','montant':'Montant (€)','commentaire':'Commentaire'
                        }),
                        use_container_width=True, hide_index=True,
                        column_config={"Montant (€)": st.column_config.NumberColumn(format="%,.2f")}
                    )

                    # Résumé par chantier
                    if 'objet' in tv_df.columns and tv_df['objet'].notna().any():
                        st.subheader("Résumé par chantier")
                        by_obj = tv_df.groupby('objet')['montant'].agg(['sum','count']).reset_index()
                        by_obj.columns = ['Chantier','Total (€)','Nb factures']
                        by_obj = by_obj.sort_values('Total (€)', ascending=False)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.dataframe(by_obj, use_container_width=True, hide_index=True,
                                column_config={"Total (€)": st.column_config.NumberColumn(format="%,.2f")})
                        with col2:
                            fig = px.pie(by_obj, values='Total (€)', names='Chantier',
                                title="Répartition par chantier")
                            st.plotly_chart(fig, use_container_width=True)

                    csv_tv = tv_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button("📥 Exporter CSV", csv_tv, "travaux_votes.csv", "text/csv")

            # ---- MODIFIER ----
            with subtab1b:
                st.subheader("✏️ Modifier un travail voté")
                if tv_df.empty:
                    st.info("Aucun travail voté enregistré.")
                else:
                    # Sélecteur
                    tv_labels = tv_df.apply(lambda r: (
                        f"{r['date'].strftime('%d/%m/%Y')} — "
                        f"{r.get('objet','?')} — "
                        f"{r.get('fournisseur','?')} — "
                        f"{float(r.get('montant',0)):,.2f} €"
                    ), axis=1).tolist()
                    sel_tv_label = st.selectbox("Sélectionner l'entrée à modifier", tv_labels, key="tv_mod_sel")
                    sel_tv_row   = tv_df.iloc[tv_labels.index(sel_tv_label)]
                    sel_tv_id    = int(sel_tv_row['id'])
                    is_transferee = pd.notna(sel_tv_row.get('depense_id'))

                    if is_transferee:
                        st.info("🔗 Cette entrée est une facture transférée. "
                                "Seul l'**objet / chantier** et le **commentaire** sont modifiables "
                                "(les montants et dates viennent de la dépense source).")

                    with st.form(f"form_mod_tv_{sel_tv_id}"):
                        mc1, mc2 = st.columns(2)
                        with mc1:
                            m_objet = st.text_input(
                                "Objet / Chantier *",
                                value=str(sel_tv_row.get('objet','') or ''),
                                key=f"tvm_obj_{sel_tv_id}"
                            )
                            m_fourn = st.text_input(
                                "Fournisseur",
                                value=str(sel_tv_row.get('fournisseur','') or ''),
                                disabled=is_transferee,
                                key=f"tvm_fourn_{sel_tv_id}"
                            )
                        with mc2:
                            m_date = st.date_input(
                                "Date",
                                value=sel_tv_row['date'].date() if pd.notna(sel_tv_row.get('date')) else datetime.now().date(),
                                disabled=is_transferee,
                                key=f"tvm_date_{sel_tv_id}"
                            )
                            m_montant = st.number_input(
                                "Montant (€)",
                                value=float(sel_tv_row.get('montant',0) or 0),
                                disabled=is_transferee,
                                key=f"tvm_mont_{sel_tv_id}"
                            )
                        m_comment = st.text_input(
                            "Commentaire",
                            value=str(sel_tv_row.get('commentaire','') or ''),
                            key=f"tvm_com_{sel_tv_id}"
                        )

                        if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
                            if not m_objet.strip():
                                st.error("❌ L'objet / chantier est obligatoire.")
                            else:
                                try:
                                    updates = {
                                        'objet':       m_objet.strip(),
                                        'commentaire': m_comment.strip() or None,
                                    }
                                    if not is_transferee:
                                        updates['fournisseur'] = m_fourn.strip() or None
                                        updates['date']        = m_date.strftime('%Y-%m-%d')
                                        updates['montant']     = float(m_montant)
                                    supabase.table('travaux_votes').update(updates).eq('id', sel_tv_id).execute()
                                    st.success("✅ Entrée mise à jour.")
                                    st.cache_data.clear(); st.rerun()
                                except Exception as e:
                                    st.error(f"❌ {e}")

                        # ---- NOUVEAU CHANTIER / SAISIE MANUELLE ----
            with subtab2:
                st.subheader("Ajouter une dépense de travaux votés")
                with st.form("form_tv"):
                    col1, col2 = st.columns(2)
                    with col1:
                        tv_date = st.date_input("Date de la facture *", value=datetime.now())
                        tv_objet = st.text_input("Objet / Chantier *",
                            placeholder="Ex: Ravalement façade, Remplacement ascenseur...")
                        tv_fournisseur = st.text_input("Fournisseur *")
                    with col2:
                        tv_montant = st.number_input("Montant (€) *", min_value=0.0, step=0.01, format="%.2f")
                        tv_ag = st.text_input("AG de vote", placeholder="Ex: AG du 15/03/2024")
                        tv_comment = st.text_area("Commentaire")

                    if st.form_submit_button("✨ Enregistrer", type="primary", use_container_width=True):
                        if tv_objet and tv_fournisseur and tv_montant > 0:
                            try:
                                supabase.table('travaux_votes').insert({
                                    'date': tv_date.strftime('%Y-%m-%d'),
                                    'objet': tv_objet.strip(),
                                    'fournisseur': tv_fournisseur.strip(),
                                    'montant': float(tv_montant),
                                    'ag_vote': tv_ag.strip() if tv_ag else None,
                                    'commentaire': tv_comment.strip() if tv_comment else None,
                                    'depense_id': None
                                }).execute()
                                st.success("✅ Travaux enregistrés!"); st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")
                        else:
                            st.error("❌ Remplissez tous les champs obligatoires")

            # ---- TRANSFÉRER FACTURES ----
            with subtab3:
                st.subheader("🔗 Transférer des factures depuis les Dépenses courantes")
                st.caption("Les factures transférées restent dans la table Dépenses mais sont marquées comme "
                           "travaux votés et **exclues des charges courantes** (5ème appel).")

                # Filtrer les dépenses non encore transférées
                dep_non_tv = dep_f[~dep_f['id'].isin(tv_dep_ids)].copy()
                dep_deja_tv = dep_f[dep_f['id'].isin(tv_dep_ids)].copy()

                col1, col2 = st.columns(2)
                col1.metric("Dépenses transférables", len(dep_non_tv))
                col2.metric("Déjà transférées (cette année)", len(dep_deja_tv),
                    delta=f"{dep_deja_tv['montant_du'].sum():,.2f} €")

                if dep_non_tv.empty:
                    st.info("Toutes les dépenses de cette année sont déjà transférées.")
                else:
                    # Champ objet / AG en haut
                    col1, col2 = st.columns(2)
                    with col1:
                        tv_objet_tr = st.text_input("Objet / Chantier *",
                            placeholder="Ex: Ravalement façade 2025", key="tv_objet_tr")
                    with col2:
                        tv_ag_tr = st.text_input("AG de vote",
                            placeholder="Ex: AG du 15/03/2024", key="tv_ag_tr")

                    st.caption("✅ Cochez les factures à transférer puis cliquez sur le bouton.")

                    # Tableau éditable avec case à cocher — c'est la SEULE façon d'avoir des cases interactives
                    dep_editor = dep_non_tv[['id','date','fournisseur','montant_du','classe','commentaire']].copy()
                    dep_editor['date'] = dep_editor['date'].dt.strftime('%d/%m/%Y')
                    dep_editor['compte'] = dep_non_tv['compte'].astype(str).fillna('') if 'compte' in dep_non_tv.columns else ''
                    dep_editor['fournisseur'] = dep_editor['fournisseur'].astype(str).fillna('')
                    dep_editor['commentaire'] = dep_editor['commentaire'].astype(str).fillna('').replace('None','')
                    dep_editor['montant_du'] = pd.to_numeric(dep_editor['montant_du'], errors='coerce').fillna(0.0)
                    dep_editor['✓ Transférer'] = False  # case à cocher initiale

                    edited_tv = st.data_editor(
                        dep_editor[['✓ Transférer','date','fournisseur','compte','montant_du','classe','commentaire']],
                        use_container_width=True, hide_index=True,
                        disabled=['date','fournisseur','compte','montant_du','classe','commentaire'],
                        column_config={
                            '✓ Transférer': st.column_config.CheckboxColumn("✓", help="Cocher pour transférer"),
                            'montant_du': st.column_config.NumberColumn("Montant (€)", format="%,.2f"),
                            'date': st.column_config.TextColumn("Date"),
                            'fournisseur': st.column_config.TextColumn("Fournisseur"),
                            'compte': st.column_config.TextColumn("Compte"),
                            'classe': st.column_config.TextColumn("Classe"),
                            'commentaire': st.column_config.TextColumn("Commentaire"),
                        }, key="tv_dep_editor"
                    )

                    # Récupérer les IDs cochés
                    ids_tv_sel = dep_non_tv['id'].values[edited_tv['✓ Transférer'].values]

                    if len(ids_tv_sel) > 0:
                        total_sel_tv = dep_non_tv[dep_non_tv['id'].isin(ids_tv_sel)]['montant_du'].sum()
                        st.info(f"**{len(ids_tv_sel)}** facture(s) sélectionnée(s) — **{total_sel_tv:,.2f} €**")

                    if st.button("🔗 Transférer en Travaux Votés", type="primary",
                                 disabled=(len(ids_tv_sel) == 0)):
                        if not tv_objet_tr:
                            st.error("❌ Saisissez l'objet du chantier")
                        else:
                            try:
                                for dep_id in ids_tv_sel:
                                    dep_row = dep_non_tv[dep_non_tv['id'] == dep_id].iloc[0]
                                    supabase.table('travaux_votes').insert({
                                        'date': dep_row['date'].strftime('%Y-%m-%d'),
                                        'objet': tv_objet_tr.strip(),
                                        'fournisseur': dep_row['fournisseur'],
                                        'montant': float(dep_row['montant_du']),
                                        'ag_vote': tv_ag_tr.strip() if tv_ag_tr else None,
                                        'commentaire': str(dep_row.get('commentaire','') or ''),
                                        'depense_id': int(dep_id)
                                    }).execute()
                                st.success(f"✅ {len(ids_tv_sel)} facture(s) transférée(s)!"); st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

                # Retransférer (annuler un transfert)
                if not dep_deja_tv.empty:
                    st.divider()
                    st.subheader("↩️ Annuler un transfert")
                    ids_annul = st.multiselect(
                        "Factures à ré-intégrer dans les charges courantes",
                        options=dep_deja_tv['id'].tolist(),
                        format_func=lambda x: (
                            f"{dep_deja_tv[dep_deja_tv['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                            f"{dep_deja_tv[dep_deja_tv['id']==x]['fournisseur'].values[0]} — "
                            f"{dep_deja_tv[dep_deja_tv['id']==x]['montant_du'].values[0]:,.2f} €"
                        ), key="tv_annul"
                    )
                    if ids_annul and st.button("↩️ Annuler le transfert", type="secondary"):
                        try:
                            for dep_id in ids_annul:
                                supabase.table('travaux_votes').delete().eq('depense_id', dep_id).execute()
                            st.success(f"✅ {len(ids_annul)} transfert(s) annulé(s)"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

            # ---- GÉRER ----
            with subtab4:
                st.warning("⚠️ La suppression est définitive.")
                if tv_df.empty:
                    st.info("Aucun travail voté enregistré.")
                else:
                    tv_manuels = tv_df[tv_df['depense_id'].isna()] if 'depense_id' in tv_df.columns else tv_df
                    if not tv_manuels.empty:
                        ids_tv_del = st.multiselect("Supprimer des entrées manuelles",
                            options=tv_manuels['id'].tolist(),
                            format_func=lambda x: (
                                f"{tv_manuels[tv_manuels['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                                f"{tv_manuels[tv_manuels['id']==x]['objet'].values[0]} — "
                                f"{tv_manuels[tv_manuels['id']==x]['montant'].values[0]:,.2f} €"
                            ))
                        if ids_tv_del and st.button("🗑️ Supprimer", type="secondary", key="del_tv"):
                            for i in ids_tv_del:
                                supabase.table('travaux_votes').delete().eq('id', i).execute()
                            st.success(f"✅ {len(ids_tv_del)} supprimé(s)"); st.rerun()
                    else:
                        st.info("Toutes les entrées sont des transferts (à annuler via l'onglet 🔗).")

        # ==================== TAB6 : FACTURES ====================
        with tab6:
            st.subheader("📎 Factures — vue par dépense")
            st.caption("Cliquez sur une dépense pour afficher, uploader ou supprimer la facture associée.")

            if dep_f.empty:
                st.info("Aucune dépense pour cette période.")
            else:
                # Préparer la liste des dépenses avec indicateur facture
                dep_fac = dep_f.copy()
                dep_fac['montant_du'] = pd.to_numeric(dep_fac['montant_du'], errors='coerce').fillna(0)
                dep_fac['date_fmt'] = dep_fac['date'].dt.strftime('%d/%m/%Y')
                has_facture = (
                    dep_fac['facture_path'].apply(
                        lambda x: bool(x) and str(x) not in ('', 'None', 'nan', 'NaN')
                    ).fillna(False).astype(bool)
                ) if 'facture_path' in dep_fac.columns else pd.Series([False] * len(dep_fac), dtype=bool)

                # Filtre par statut facture
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    fac_filter = st.radio("Afficher", ["Toutes", "✅ Avec facture", "❌ Sans facture"],
                        horizontal=True, key="fac_filter")
                with col_f2:
                    fac_search = st.text_input("🔍 Recherche fournisseur", key="fac_search")

                dep_fac_show = dep_fac.copy()
                if fac_filter == "✅ Avec facture":
                    dep_fac_show = dep_fac_show[has_facture]
                elif fac_filter == "❌ Sans facture":
                    dep_fac_show = dep_fac_show[~has_facture]
                if fac_search:
                    dep_fac_show = dep_fac_show[
                        dep_fac_show['fournisseur'].astype(str).str.contains(fac_search, case=False, na=False)
                    ]

                dep_fac_show = dep_fac_show.sort_values('date', ascending=False)

                # Métriques
                total_avec = has_facture.sum()
                total_sans = len(dep_fac) - total_avec
                m1, m2, m3 = st.columns(3)
                m1.metric("Total dépenses", len(dep_fac))
                m2.metric("✅ Avec facture", total_avec)
                m3.metric("❌ Sans facture", total_sans)
                st.divider()

                # Affichage dépense par dépense
                for _, row in dep_fac_show.iterrows():
                    dep_id = int(row['id'])
                    fp = row.get('facture_path','')
                    a_facture = fp and str(fp) not in ('','None','nan')

                    # En-tête de la ligne
                    badge = "✅" if a_facture else "❌"
                    with st.expander(
                        f"{badge} {row['date_fmt']} | {row['fournisseur']} | "
                        f"{row['montant_du']:,.2f} € | {row.get('libelle_compte','')[:40]}",
                        expanded=False
                    ):
                        col_dep, col_fac = st.columns([1, 2])

                        # ── Colonne gauche : infos dépense ──
                        with col_dep:
                            st.markdown("**📄 Dépense**")
                            st.markdown(f"""
| Champ | Valeur |
|---|---|
| **Date** | {row['date_fmt']} |
| **Compte** | {row.get('compte','')} |
| **Libellé** | {row.get('libelle_compte','')[:45]} |
| **Fournisseur** | {row.get('fournisseur','')} |
| **Montant** | **{row['montant_du']:,.2f} €** |
| **Classe** | {row.get('classe','')} |
| **Commentaire** | {row.get('commentaire','') or '—'} |
""")
                            # Upload facture
                            st.markdown("---")
                            uploaded = st.file_uploader(
                                "📤 Uploader la facture",
                                type=['pdf','png','jpg','jpeg','webp'],
                                key=f"upload_detail_{dep_id}",
                                label_visibility="visible"
                            )
                            if uploaded:
                                col_u1, col_u2 = st.columns(2)
                                with col_u1:
                                    if st.button("💾 Enregistrer la facture", key=f"save_fac_{dep_id}",
                                                 use_container_width=True, type="primary"):
                                        try:
                                            upload_facture(dep_id, uploaded.getvalue(), uploaded.name)
                                            st.success("✅ Facture enregistrée.")
                                            st.cache_data.clear(); st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ {e}")

                            # Supprimer facture
                            if a_facture:
                                if st.button("🗑️ Supprimer la facture", key=f"del_fac_{dep_id}",
                                             use_container_width=True):
                                    try:
                                        delete_facture(dep_id, str(fp))
                                        st.success("✅ Facture supprimée.")
                                        st.cache_data.clear(); st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ {e}")

                        # ── Colonne droite : aperçu facture ──
                        with col_fac:
                            st.markdown("**🧾 Facture**")
                            if a_facture:
                                afficher_facture(str(fp), height=500)
                            else:
                                st.markdown(
                                    "<div style='height:200px;border:2px dashed #555;border-radius:8px;"
                                    "display:flex;align-items:center;justify-content:center;"
                                    "color:#888;font-size:1.1em;'>"
                                    "📂 Aucune facture — uploadez-en une à gauche"
                                    "</div>",
                                    unsafe_allow_html=True
                                )

    else:
        st.info("💡 Aucune dépense. Utilisez l'onglet ➕ Ajouter.")

# ==================== COPROPRIÉTAIRES ====================
elif menu == "👥 Copropriétaires":
    st.markdown("<h1 class='main-header'>👥 Copropriétaires</h1>", unsafe_allow_html=True)
    copro_df = get_coproprietaires()

    if not copro_df.empty:
        copro_df = prepare_copro(copro_df)
        tantieme_cols = ['tantieme_general','tantieme_ascenseurs','tantieme_rdc_ssols','tantieme_garages','tantieme_ssols','tantieme_monte_voitures']

        # S'assurer que les colonnes contact existent
        for col_c in ['email','telephone','whatsapp']:
            if col_c not in copro_df.columns:
                copro_df[col_c] = None if col_c != 'whatsapp' else False

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Copropriétaires", len(copro_df))
        c2.metric("Total tantièmes généraux", int(copro_df['tantieme_general'].sum()))
        c3.metric("Lots parkings", len(copro_df[copro_df['usage']=='parking']) if 'usage' in copro_df.columns else "—")
        nb_wa = int(copro_df['whatsapp'].fillna(False).astype(bool).sum())
        c4.metric("💬 WhatsApp", nb_wa)

        copro_tab1, copro_tab2, copro_tab3 = st.tabs(["📋 Liste", "📞 Contacts", "🔑 Tantièmes"])

        # ── TAB 1 : Liste complète ──────────────────────────────────
        with copro_tab1:
            st.subheader("Liste des copropriétaires")
            disp_cols_base = ['lot','nom','etage','usage','tantieme_general']
            contact_disp = [c for c in ['email','telephone','whatsapp'] if c in copro_df.columns]
            disp_cols = disp_cols_base + contact_disp
            df_disp = copro_df[disp_cols].sort_values('lot' if 'lot' in copro_df.columns else 'nom').copy()
            if 'whatsapp' in df_disp.columns:
                df_disp['whatsapp'] = df_disp['whatsapp'].fillna(False).astype(bool)

            st.dataframe(
                df_disp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'lot':              st.column_config.NumberColumn("Lot", format="%d"),
                    'nom':              st.column_config.TextColumn("Nom"),
                    'etage':            st.column_config.TextColumn("Étage"),
                    'usage':            st.column_config.TextColumn("Usage"),
                    'tantieme_general': st.column_config.NumberColumn("Tantièmes généraux", format="%d"),
                    'email':            st.column_config.TextColumn("📧 Email"),
                    'telephone':        st.column_config.TextColumn("📱 Téléphone"),
                    'whatsapp':         st.column_config.CheckboxColumn("💬 WhatsApp"),
                }
            )

            # Export CSV
            csv_copro = df_disp.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button("📥 Exporter CSV", data=csv_copro,
                               file_name="coproprietaires.csv", mime="text/csv", key="dl_copro")

        # ── TAB 2 : Contacts (édition mail/tel/whatsapp) ───────────
        with copro_tab2:
            st.subheader("📞 Coordonnées & WhatsApp")
            st.caption("Cliquez sur une cellule pour modifier directement. Enregistrez ligne par ligne.")

            # Sélecteur copropriétaire
            noms_sorted = sorted(copro_df['nom'].tolist())
            sel_nom = st.selectbox("Sélectionner un copropriétaire", noms_sorted, key="sel_contact")
            row_sel = copro_df[copro_df['nom'] == sel_nom].iloc[0]
            cop_id  = int(row_sel['id'])

            st.divider()
            col_c1, col_c2, col_c3 = st.columns([3,3,1])
            with col_c1:
                new_email = st.text_input("📧 Email", value=str(row_sel.get('email','') or ''),
                                          key=f"email_{cop_id}", placeholder="prenom.nom@email.com")
            with col_c2:
                new_tel = st.text_input("📱 Téléphone", value=str(row_sel.get('telephone','') or ''),
                                        key=f"tel_{cop_id}", placeholder="+33 6 00 00 00 00")
            with col_c3:
                st.markdown("<br>", unsafe_allow_html=True)
                new_wa = st.checkbox("💬 WhatsApp", value=bool(row_sel.get('whatsapp', False)),
                                     key=f"wa_{cop_id}")

            if st.button("💾 Enregistrer les coordonnées", key=f"save_contact_{cop_id}",
                         type="primary", use_container_width=True):
                try:
                    updates = {
                        'email':     new_email.strip() or None,
                        'telephone': new_tel.strip() or None,
                        'whatsapp':  new_wa,
                    }
                    supabase.table('coproprietaires').update(updates).eq('id', cop_id).execute()
                    st.success(f"✅ Coordonnées de **{sel_nom}** enregistrées.")
                    st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

            st.divider()
            st.subheader("📋 Annuaire complet")
            # Tableau annuaire complet lecture seule
            annuaire = copro_df[['lot','nom','email','telephone','whatsapp']].copy()
            annuaire = annuaire.sort_values('lot')
            annuaire['whatsapp'] = annuaire['whatsapp'].fillna(False).astype(bool)
            # Indicateurs
            nb_email = annuaire['email'].apply(lambda x: bool(x) and str(x) not in ('','None','nan')).sum()
            nb_tel   = annuaire['telephone'].apply(lambda x: bool(x) and str(x) not in ('','None','nan')).sum()
            ann1, ann2, ann3 = st.columns(3)
            ann1.metric("📧 Avec email",     f"{nb_email}/{len(annuaire)}")
            ann2.metric("📱 Avec téléphone", f"{nb_tel}/{len(annuaire)}")
            ann3.metric("💬 WhatsApp",       f"{nb_wa}/{len(annuaire)}")

            st.dataframe(
                annuaire,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'lot':       st.column_config.NumberColumn("Lot", format="%d"),
                    'nom':       st.column_config.TextColumn("Nom"),
                    'email':     st.column_config.TextColumn("📧 Email"),
                    'telephone': st.column_config.TextColumn("📱 Téléphone"),
                    'whatsapp':  st.column_config.CheckboxColumn("💬 WhatsApp"),
                }
            )

            # Export annuaire CSV
            csv_ann = annuaire.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button("📥 Exporter l'annuaire CSV", data=csv_ann,
                               file_name="annuaire_copro.csv", mime="text/csv", key="dl_ann")

        # ── TAB 3 : Tantièmes ───────────────────────────────────────
        with copro_tab3:
            st.divider()
            # Vérifier si les tantièmes spécifiques sont remplis
            remplis = {col: int(copro_df[col].sum()) for col in tantieme_cols if col in copro_df.columns}
            st.subheader("🔑 État des clés de répartition")
            cols = st.columns(len(remplis))
            for i, (col, total) in enumerate(remplis.items()):
                label = col.replace('tantieme_','').replace('_',' ').title()
                status = "✅" if total > 0 else "⚠️ À remplir"
                cols[i].metric(f"{status} {label}", f"{total:,}")

            if any(v == 0 for v in remplis.values()):
                st.warning("⚠️ Certains tantièmes sont à 0. Exécutez **UPDATE_TANTIEMES.sql** dans Supabase pour les remplir.")

            st.divider()
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Répartition des tantièmes généraux")
                fig = px.pie(copro_df, values='tantieme_general', names='nom')
                fig.update_traces(textposition='inside', textinfo='percent')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.subheader("Tantièmes par copropriétaire")
                tant_cols_disp = ['lot','nom'] + [c for c in tantieme_cols if c in copro_df.columns]
                st.dataframe(copro_df[tant_cols_disp].sort_values('lot' if 'lot' in copro_df.columns else 'nom'),
                    use_container_width=True, hide_index=True)

# ==================== RÉPARTITION ====================
elif menu == "🔄 Répartition":
    st.markdown("<h1 class='main-header'>🔄 Appels de Fonds & Répartition</h1>", unsafe_allow_html=True)

    copro_df = get_coproprietaires()
    budget_df = get_budget()
    depenses_df = get_depenses()

    if copro_df.empty:
        st.error("❌ Impossible de charger les copropriétaires"); st.stop()

    copro_df = prepare_copro(copro_df)

    # Vérifier état des tantièmes
    tantieme_ok = copro_df['tantieme_general'].sum() > 0
    autres_ok = any(copro_df.get(CHARGES_CONFIG[k]['col'], pd.Series([0])).sum() > 0 for k in ['ascenseurs','rdc_ssols','garages','ssols'])

    if not autres_ok:
        st.warning("⚠️ Les tantièmes spécifiques (ascenseurs, garages, etc.) sont à 0. Exécutez **UPDATE_TANTIEMES.sql** dans Supabase. En attendant, tout est réparti sur les tantièmes généraux.")
        # Fallback temporaire
        for key in ['ascenseurs','rdc_ssols','garages','ssols']:
            col = CHARGES_CONFIG[key]['col']
            if col not in copro_df.columns or copro_df[col].sum() == 0:
                copro_df[col] = copro_df['tantieme_general']

    tab1, tab2, tab3 = st.tabs([
        "📅 Appels provisionnels (T1/T2/T3/T4)",
        "🔄 5ème appel — Régularisation",
        "📊 Vue globale annuelle"
    ])

    # ---- Budget sélectionné ----
    if not budget_df.empty:
        annees_bud = sorted(budget_df['annee'].unique(), reverse=True)
    else:
        annees_bud = [datetime.now().year]

    # ==================== ONGLET 1 : APPELS PROVISIONNELS ====================
    with tab1:
        st.subheader("Calcul des appels de fonds provisionnels")
        st.info("Les appels sont calculés sur le **budget prévisionnel**, réparti selon les clés de tantièmes de votre règlement de copropriété.")

        col1, col2, col3 = st.columns(3)
        with col1:
            annee_appel = st.selectbox("📅 Année", annees_bud, key="appel_annee")
        with col2:
            trimestre = st.selectbox("📆 Appel", ["T1 — Janvier","T2 — Avril","T3 — Juillet","T4 — Octobre"], key="appel_trim")
        with col3:
            nb_appels = st.selectbox("Nb appels / an", [4, 3, 2, 1], index=0, key="nb_appels")

        label_trim = trimestre.split(" ")[0]

        if budget_df.empty:
            st.warning("⚠️ Aucun budget. Créez-en un dans 💰 Budget.")
        else:
            bud_an = budget_df[budget_df['annee'] == annee_appel]
            if bud_an.empty:
                st.warning(f"⚠️ Aucun budget pour {annee_appel}.")
            else:
                # Budget TOTAL voté en AG — sert de base pour le calcul Alur
                total_bud = float(bud_an['montant_budget'].sum())

                # Montants par type basé sur les classes du budget
                montants_auto = {}
                for key, cfg in CHARGES_CONFIG.items():
                    montants_auto[key] = float(bud_an[bud_an['classe'].isin(cfg['classes'])]['montant_budget'].sum())
                # Classes non mappées → ajoutées aux charges générales
                total_mappe = sum(montants_auto.values())
                if total_bud - total_mappe > 0.01:
                    montants_auto['general'] = montants_auto.get('general', 0) + (total_bud - total_mappe)

                st.divider()
                st.subheader(f"⚙️ Montants annuels par type de charge — Budget {annee_appel}")
                st.caption("Calculés automatiquement depuis votre budget. Vous pouvez les ajuster.")

                col1, col2, col3 = st.columns(3)
                montants = {}
                items = list(CHARGES_CONFIG.items())
                for i, (key, cfg) in enumerate(items):
                    col = [col1, col2, col3][i % 3]
                    with col:
                        montants[key] = st.number_input(
                            f"{cfg['emoji']} {cfg['label']} (€/an)",
                            min_value=0, value=int(montants_auto.get(key, 0)),
                            step=100, key=f"mont_{key}",
                            help=f"Réparti sur {cfg['total']:,} tantièmes — Classes : {', '.join(cfg['classes'])}"
                        )

                total_configure = sum(montants.values())

                st.divider()

                # ---- LOI ALUR ----
                st.subheader("🏛️ Loi Alur — Fonds de travaux")
                st.caption("Cotisation obligatoire = 5% minimum du budget prévisionnel, répartie sur les tantièmes généraux.")
                col1, col2, col3 = st.columns(3)
                with col1:
                    alur_taux = st.number_input("Taux Alur (%)", min_value=5.0, max_value=20.0,
                        value=5.0, step=0.5, key="alur_taux",
                        help="Minimum légal = 5% du budget prévisionnel voté en AG (loi Alur art. 14-2)")
                with col2:
                    # BASE CORRECTE : budget total voté (total_bud), pas les montants configurés
                    alur_annuel = round(total_bud * alur_taux / 100, 2)
                    st.metric("Fonds de travaux annuel", f"{alur_annuel:,.2f} €",
                        help=f"{alur_taux}% × {total_bud:,.0f} € (budget voté en AG)")
                with col3:
                    alur_par_appel = round(alur_annuel / nb_appels, 2)
                    st.metric(f"Alur par appel ({label_trim})", f"{alur_par_appel:,.2f} €")

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Budget charges", f"{total_configure:,.0f} €")
                c2.metric("Fonds de travaux (Alur)", f"{alur_annuel:,.2f} €")
                total_avec_alur = total_configure + alur_annuel
                c3.metric("Total appel annuel", f"{total_avec_alur:,.2f} €")
                ecart_cfg = total_configure - total_bud
                c4.metric("Écart vs budget", f"{ecart_cfg:+,.0f} €",
                    delta_color="normal" if abs(ecart_cfg) < 100 else "inverse")

                if abs(ecart_cfg) > 500:
                    st.warning(f"⚠️ Différence de {abs(ecart_cfg):,.0f} € entre le total configuré et le budget.")

                st.divider()
                st.subheader(f"📋 Appel {label_trim} {annee_appel} — {100//nb_appels}% du budget annuel + Alur")

                # Calcul charges + Alur
                appels_df = calculer_appels(copro_df, montants)
                appels_df[f'🎯 APPEL {label_trim} (€)'] = (appels_df['💰 TOTAL Annuel (€)'] / nb_appels).round(2)

                # Ajouter la cotisation Alur (répartie sur tantièmes généraux /10000)
                # Utilise _tantieme_general stocké directement dans appels_df (évite le lookup par nom bugué)
                appels_df['🏛️ Alur (€)'] = (appels_df['_tantieme_general'] / 10000 * alur_par_appel).round(2)
                appels_df[f'🎯 TOTAL {label_trim} avec Alur (€)'] = (
                    appels_df[f'🎯 APPEL {label_trim} (€)'] + appels_df['🏛️ Alur (€)']
                ).round(2)

                show_detail = st.checkbox("Afficher le détail par type de charge", value=False, key="show_det")

                # Supprimer la colonne technique avant affichage
                if '_tantieme_general' in appels_df.columns:
                    appels_df = appels_df.drop(columns=['_tantieme_general'])
                detail_cols = [f"{CHARGES_CONFIG[k]['emoji']} {CHARGES_CONFIG[k]['label']}" for k in CHARGES_CONFIG]
                base_cols = ['Lot','Copropriétaire','Étage','Usage']
                alur_cols = ['🏛️ Alur (€)', f'🎯 TOTAL {label_trim} avec Alur (€)']
                if show_detail:
                    display_cols = base_cols + detail_cols + ['💰 TOTAL Annuel (€)', f'🎯 APPEL {label_trim} (€)'] + alur_cols
                else:
                    display_cols = base_cols + ['💰 TOTAL Annuel (€)', f'🎯 APPEL {label_trim} (€)'] + alur_cols

                display_cols = [c for c in display_cols if c in appels_df.columns]

                st.dataframe(appels_df[display_cols], use_container_width=True, hide_index=True,
                    column_config={
                        f'🎯 APPEL {label_trim} (€)': st.column_config.NumberColumn("Charges (€)", format="%.2f"),
                        '🏛️ Alur (€)': st.column_config.NumberColumn("Alur (€)", format="%.2f"),
                        f'🎯 TOTAL {label_trim} avec Alur (€)': st.column_config.NumberColumn(f"🎯 TOTAL {label_trim} (€)", format="%.2f"),
                        '💰 TOTAL Annuel (€)': st.column_config.NumberColumn("Total Annuel (€)", format="%.2f"),
                    })

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                total_charges = appels_df[f'🎯 APPEL {label_trim} (€)'].sum()
                total_alur_appel = appels_df['🏛️ Alur (€)'].sum()
                total_avec_alur = appels_df[f'🎯 TOTAL {label_trim} avec Alur (€)'].sum()
                c1.metric(f"Charges {label_trim}", f"{total_charges:,.2f} €")
                c2.metric("Fonds Alur", f"{total_alur_appel:,.2f} €")
                c3.metric(f"🎯 TOTAL {label_trim}", f"{total_avec_alur:,.2f} €")
                c4.metric("Appel moyen / copro", f"{total_avec_alur/len(appels_df):,.2f} €")

                csv_appel = appels_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

                # ---- EXPORT CSV + PDF ----
                col_exp1, col_exp2, col_exp3 = st.columns(3)
                with col_exp1:
                    st.download_button(
                        f"📥 CSV — Appel {label_trim} {annee_appel}",
                        csv_appel, f"appel_{label_trim}_{annee_appel}.csv", "text/csv"
                    )

                with col_exp2:
                    # PDF individuel : sélection d'un copropriétaire
                    noms_copros = appels_df['Copropriétaire'].tolist()
                    copro_sel_pdf = st.selectbox(
                        "📄 PDF individuel — Copropriétaire",
                        options=noms_copros,
                        key="pdf_copro_sel"
                    )
                    if st.button("📄 Générer PDF individuel", key="btn_pdf_indiv"):
                        cop_row_pdf = copro_df[copro_df['nom'] == copro_sel_pdf].iloc[0] if len(copro_df[copro_df['nom'] == copro_sel_pdf]) > 0 else None
                        if cop_row_pdf is not None:
                            mois_debut = {'T1':'01/01','T2':'01/04','T3':'01/07','T4':'01/10'}[label_trim]
                            mois_fin   = {'T1':'31/03','T2':'30/06','T3':'30/09','T4':'31/12'}[label_trim]
                            periode_pdf = f"{mois_debut}/{annee_appel} au {mois_fin}/{annee_appel}"
                            pdf_bytes = generate_appel_pdf_bytes(
                                SYNDIC_INFO, cop_row_pdf.to_dict(), periode_pdf,
                                label_trim, annee_appel, montants, alur_par_appel, nb_appels
                            )
                            st.download_button(
                                f"⬇️ Télécharger PDF — {copro_sel_pdf}",
                                pdf_bytes,
                                f"appel_{label_trim}_{annee_appel}_{cop_row_pdf.get('lot','')}.pdf",
                                "application/pdf",
                                key="dl_pdf_indiv"
                            )
                        else:
                            st.error("Copropriétaire non trouvé")

                with col_exp3:
                    # PDF tous les copropriétaires (fusionné)
                    if st.button("📦 Générer tous les PDFs (ZIP)", key="btn_pdf_all"):
                        import zipfile, io as _io
                        mois_debut = {'T1':'01/01','T2':'01/04','T3':'01/07','T4':'01/10'}[label_trim]
                        mois_fin   = {'T1':'31/03','T2':'30/06','T3':'30/09','T4':'31/12'}[label_trim]
                        periode_pdf = f"{mois_debut}/{annee_appel} au {mois_fin}/{annee_appel}"

                        zip_buf = _io.BytesIO()
                        nb_gen = 0
                        with st.spinner(f"Génération des PDFs en cours..."):
                            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for _, cop_row_pdf in copro_df.iterrows():
                                    try:
                                        pdf_b = generate_appel_pdf_bytes(
                                            SYNDIC_INFO, cop_row_pdf.to_dict(), periode_pdf,
                                            label_trim, annee_appel, montants, alur_par_appel, nb_appels
                                        )
                                        fname = f"appel_{label_trim}_{annee_appel}_lot{str(cop_row_pdf.get('lot','')).zfill(4)}.pdf"
                                        zf.writestr(fname, pdf_b)
                                        nb_gen += 1
                                    except Exception as e_pdf:
                                        st.warning(f"⚠️ Erreur lot {cop_row_pdf.get('lot','?')}: {e_pdf}")
                        zip_buf.seek(0)
                        st.success(f"✅ {nb_gen} PDFs générés")
                        st.download_button(
                            f"⬇️ Télécharger ZIP ({nb_gen} PDFs)",
                            zip_buf.getvalue(),
                            f"appels_{label_trim}_{annee_appel}.zip",
                            "application/zip",
                            key="dl_zip_all"
                        )

                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    top15 = appels_df.nlargest(15, f'🎯 APPEL {label_trim} (€)')
                    fig = px.bar(top15, x='Copropriétaire', y=f'🎯 APPEL {label_trim} (€)',
                        color='Usage', title=f"Top 15 — Appel {label_trim} {annee_appel}",
                        text=f'🎯 APPEL {label_trim} (€)')
                    fig.update_traces(texttemplate='%{text:.0f}€', textposition='outside')
                    fig.update_layout(xaxis_tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    type_data = pd.DataFrame([
                        {'Type': f"{cfg['emoji']} {cfg['label']}", 'Montant': montants[k]}
                        for k, cfg in CHARGES_CONFIG.items() if montants[k] > 0
                    ])
                    if not type_data.empty:
                        fig = px.pie(type_data, values='Montant', names='Type', title="Répartition par type de charge")
                        st.plotly_chart(fig, use_container_width=True)

    # ==================== ONGLET 2 : 5ÈME APPEL RÉGULARISATION ====================
    with tab2:
        st.subheader("5ème appel — Régularisation sur dépenses réelles")
        st.info("""
        **Principe :** Appels de fonds = Budget_type × (tantièmes_copro / total)  
        Charges réelles = Dépenses_réelles_type × (tantièmes_copro / total)  
        **5ème appel = Charges réelles − Appels de fonds versés**  
        → Positif = complément à payer | Négatif = remboursement
        """)

        col1, col2, col3 = st.columns(3)
        with col1:
            annee_reg = st.selectbox("📅 Année à régulariser", annees_bud, key="reg_annee")
        with col2:
            nb_appels_reg = st.selectbox("Nb appels provisionnels versés", [4,3,2,1], key="nb_reg",
                help="Nombre d'appels provisionnels déjà versés dans l'année")
        with col3:
            alur_taux_reg = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_reg")

        if depenses_df.empty:
            st.warning("⚠️ Aucune dépense disponible.")
        else:
            # Préparer dépenses réelles de l'année
            depenses_df_reg = depenses_df.copy()
            depenses_df_reg['date'] = pd.to_datetime(depenses_df_reg['date'])
            depenses_df_reg['montant_du'] = pd.to_numeric(depenses_df_reg['montant_du'], errors='coerce')
            dep_reg = depenses_df_reg[depenses_df_reg['date'].dt.year == annee_reg].copy()

            # Exclure Alur et Travaux Votés
            alur_ids_reg = get_depenses_alur_ids()
            tv_ids_reg   = get_travaux_votes_depense_ids()
            ids_exclus   = set(alur_ids_reg) | set(tv_ids_reg)
            dep_reg_net  = dep_reg[~dep_reg['id'].isin(ids_exclus)]

            montant_alur_exclus = dep_reg[dep_reg['id'].isin(alur_ids_reg)]['montant_du'].sum()
            montant_tv_exclus   = dep_reg[dep_reg['id'].isin(tv_ids_reg)]['montant_du'].sum()
            if montant_alur_exclus > 0 or montant_tv_exclus > 0:
                st.info(f"🔒 Exclus du calcul : 🏛️ Alur {montant_alur_exclus:,.2f} € | "
                        f"🏗️ Travaux votés {montant_tv_exclus:,.2f} €")

            # Dépenses réelles nettes par type
            dep_reel_type = {}
            for key, cfg in CHARGES_CONFIG.items():
                if 'classe' in dep_reg_net.columns:
                    dep_reel_type[key] = float(dep_reg_net[dep_reg_net['classe'].isin(cfg['classes'])]['montant_du'].sum())
                else:
                    dep_reel_type[key] = 0

            # Budget CSV de référence
            bud_reg = budget_df[budget_df['annee'] == annee_reg] if not budget_df.empty else pd.DataFrame()

            # ---- SAISIE DES BUDGETS APPELÉS ----
            st.divider()
            st.subheader("⚙️ Budgets annuels utilisés pour les appels de fonds")
            st.caption("Ces montants doivent correspondre exactement à ceux utilisés lors des appels T1 à T4. "
                       "Ils sont pré-remplis depuis l'onglet Appels T1-T4 si vous l'avez visité.")

            col1, col2, col3 = st.columns(3)
            budgets_appel = {}
            for i, (key, cfg) in enumerate(CHARGES_CONFIG.items()):
                # Priorité : session_state T1-T4 > budget CSV > 0
                val_ss = st.session_state.get(f"mont_{key}", None)
                if val_ss is not None:
                    val_defaut = float(val_ss)
                elif not bud_reg.empty:
                    val_defaut = float(bud_reg[bud_reg['classe'].isin(cfg['classes'])]['montant_budget'].sum())
                else:
                    val_defaut = 0.0
                with [col1, col2, col3][i % 3]:
                    budgets_appel[key] = st.number_input(
                        f"{cfg['emoji']} {cfg['label']} (€/an)",
                        min_value=0.0, value=round(val_defaut, 2),
                        step=100.0, key=f"bud_reg_{key}",
                        help=f"Total annuel réparti sur {cfg['total']} tantièmes"
                    )

            total_budget_appel = sum(budgets_appel.values())

            # Calcul Alur
            alur_annuel_reg    = round(total_budget_appel * alur_taux_reg / 100, 2)
            alur_par_appel_reg = round(alur_annuel_reg / 4, 2)
            alur_verse_reg     = round(alur_par_appel_reg * nb_appels_reg, 2)

            st.divider()

            # ---- TABLEAU RÉCAP PAR TYPE ----
            st.subheader(f"📊 Récapitulatif {annee_reg} par type de charge")

            recap = []
            for key, cfg in CHARGES_CONFIG.items():
                budget_an  = budgets_appel[key]
                dep_reel   = dep_reel_type[key]
                appels_cop = budget_an  # total appelé à tous les copros (base de répartition)
                recap.append({
                    'Type':               f"{cfg['emoji']} {cfg['label']}",
                    'Budget appelé (€)':  round(budget_an, 2),
                    'Dépenses réelles (€)': round(dep_reel, 2),
                    'Écart (€)':           round(dep_reel - budget_an, 2),
                })
            # Ligne Alur
            recap.append({
                'Type':               '🏛️ Fonds Alur',
                'Budget appelé (€)':  alur_annuel_reg,
                'Dépenses réelles (€)': alur_annuel_reg,
                'Écart (€)':           0,
            })
            recap.append({
                'Type':               '💰 TOTAL',
                'Budget appelé (€)':  round(sum(r['Budget appelé (€)'] for r in recap[:-1]), 2),
                'Dépenses réelles (€)': round(sum(r['Dépenses réelles (€)'] for r in recap[:-1]), 2),
                'Écart (€)':           round(sum(r['Écart (€)'] for r in recap[:-1]), 2),
            })

            st.dataframe(pd.DataFrame(recap), use_container_width=True, hide_index=True,
                column_config={
                    'Budget appelé (€)':    st.column_config.NumberColumn(format="%,.2f"),
                    'Dépenses réelles (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Écart (€)':            st.column_config.NumberColumn(format="%+,.2f"),
                })

            c1, c2, c3, c4 = st.columns(4)
            total_dep_reel = sum(dep_reel_type.values())
            c1.metric("Budget total appelé", f"{total_budget_appel:,.2f} €")
            c2.metric("🏛️ Alur versé (info)", f"{alur_verse_reg:,.2f} €",
                help="L'Alur ne fait pas l'objet d'une régularisation — il reste dans le fonds de travaux")
            c3.metric("Dépenses réelles nettes", f"{total_dep_reel:,.2f} €")
            c4.metric("Écart global", f"{total_dep_reel - total_budget_appel:+,.2f} €",
                delta_color="inverse" if total_dep_reel > total_budget_appel else "normal")

            if total_budget_appel == 0:
                st.warning("⚠️ Saisissez les budgets par type pour calculer la régularisation.")
            else:
                st.divider()
                st.subheader(f"📋 5ème appel de régularisation — {annee_reg}")

                # ---- CALCUL PAR COPROPRIÉTAIRE ----
                # Formule : Appels_cop   = Budget_type × (tant_cop / total_tant)
                #           Charges_cop  = Dep_reel_type × (tant_cop / total_tant)
                #           5ème appel   = Charges_cop − Appels_cop
                reg_list = []
                for _, cop in copro_df.iterrows():
                    appels_cop  = 0
                    charges_cop = 0
                    detail_app  = {}
                    detail_dep  = {}

                    for key, cfg in CHARGES_CONFIG.items():
                        tant = float(cop.get(cfg['col'], 0) or 0)
                        if cfg['total'] > 0 and tant > 0:
                            part_app = round((tant / cfg['total']) * budgets_appel[key], 2)
                            part_dep = round((tant / cfg['total']) * dep_reel_type[key], 2)
                        else:
                            part_app = 0.0
                            part_dep = 0.0
                        appels_cop  += part_app
                        charges_cop += part_dep
                        detail_app[key]  = part_app
                        detail_dep[key]  = part_dep

                    # Alur : informatif uniquement (pas de régularisation)
                    tant_gen = float(cop.get('tantieme_general', 0) or 0)
                    alur_cop = round(tant_gen / 10000 * alur_annuel_reg, 2) if tant_gen > 0 else 0

                    cinquieme = round(charges_cop - appels_cop, 2)

                    row = {
                        'Lot':                cop.get('lot', ''),
                        'Copropriétaire':    cop.get('nom', ''),
                        'Étage':             cop.get('etage', ''),
                        'Usage':             cop.get('usage', ''),
                        'Appels versés (€)': round(appels_cop, 2),
                        '🏛️ Alur versé (€)': alur_cop,
                        'Charges réelles (€)': round(charges_cop, 2),
                        '5ème appel (€)':    cinquieme,
                        'Sens': '💳 À payer' if cinquieme > 0.01 else ('💚 À rembourser' if cinquieme < -0.01 else '✅ Soldé'),
                    }
                    for key, cfg in CHARGES_CONFIG.items():
                        row[f"{cfg['emoji']} {cfg['label']}"] = detail_dep[key]
                    reg_list.append(row)

                reg_df = pd.DataFrame(reg_list).sort_values('Lot')

                col1, col2 = st.columns(2)
                with col1:
                    show_zeros = st.checkbox("Afficher les lots soldés", value=True, key="show_zeros_reg")
                with col2:
                    filtre_sens = st.selectbox("Filtrer par sens",
                        ["Tous","💳 À payer","💚 À rembourser","✅ Soldé"], key="filtre_sens")

                reg_display = reg_df.copy()
                if not show_zeros:
                    reg_display = reg_display[reg_display['5ème appel (€)'].abs() > 0.01]
                if filtre_sens != "Tous":
                    reg_display = reg_display[reg_display['Sens'] == filtre_sens]

                show_det_reg = st.checkbox("Afficher le détail par type", value=False, key="show_det_reg")
                detail_cols_reg = [f"{cfg['emoji']} {cfg['label']}" for cfg in CHARGES_CONFIG.values()]
                base_cols_reg   = ['Lot','Copropriétaire','Étage','Usage',
                                   'Appels versés (€)','🏛️ Alur versé (€)',
                                   'Charges réelles (€)','5ème appel (€)','Sens']
                if show_det_reg:
                    disp_cols = ['Lot','Copropriétaire','Étage','Usage'] + detail_cols_reg +                                 ['Appels versés (€)','🏛️ Alur versé (€)','Charges réelles (€)','5ème appel (€)','Sens']
                else:
                    disp_cols = base_cols_reg
                disp_cols = [c for c in disp_cols if c in reg_display.columns]

                num_cfg = {c: st.column_config.NumberColumn(format="%,.2f")
                           for c in disp_cols if '€' in c and c != 'Sens'}
                num_cfg['5ème appel (€)'] = st.column_config.NumberColumn(format="%+,.2f")
                st.dataframe(reg_display[disp_cols], use_container_width=True, hide_index=True,
                    column_config=num_cfg)

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total appels versés", f"{reg_df['Appels versés (€)'].sum():,.2f} €")
                c2.metric("Total charges réelles", f"{reg_df['Charges réelles (€)'].sum():,.2f} €")
                a_payer = reg_df[reg_df['5ème appel (€)'] > 0.01]['5ème appel (€)'].sum()
                a_rembourser = reg_df[reg_df['5ème appel (€)'] < -0.01]['5ème appel (€)'].sum()
                c3.metric("💳 À appeler", f"{a_payer:,.2f} €")
                c4.metric("💚 À rembourser", f"{a_rembourser:,.2f} €")

                # ── EXPORTS CSV + PDF ──────────────────────────────────────
                st.divider()
                st.subheader("📥 Export")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    csv_all = reg_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(f"📥 CSV — tous les lots",
                        csv_all, f"5eme_appel_{annee_reg}.csv", "text/csv",
                        use_container_width=True)

                with col2:
                    reg_actif = reg_df[reg_df['5ème appel (€)'].abs() > 0.01]
                    csv_actif = reg_actif.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(f"📥 CSV — lots à régulariser ({len(reg_actif)})",
                        csv_actif, f"5eme_appel_{annee_reg}_actif.csv", "text/csv",
                        use_container_width=True)

                with col3:
                    # PDF individuel
                    noms_reg = reg_df['Copropriétaire'].tolist()
                    copro_sel_reg = st.selectbox("Copropriétaire", noms_reg, key="pdf_reg_sel")
                    if st.button("📄 PDF individuel", key="btn_pdf_reg", use_container_width=True):
                        cop_match = copro_df[copro_df['nom'] == copro_sel_reg]
                        if not cop_match.empty:
                            try:
                                pdf_b = generate_regularisation_pdf_bytes(
                                    SYNDIC_INFO,
                                    cop_match.iloc[0].to_dict(),
                                    annee_reg,
                                    budgets_appel,
                                    dep_reel_type,
                                    alur_annuel_reg,
                                    nb_appels_reg,
                                )
                                lot_pdf = str(cop_match.iloc[0].get('lot', ''))
                                st.download_button(
                                    f"⬇️ {copro_sel_reg}",
                                    pdf_b,
                                    f"regularisation_{annee_reg}_lot{lot_pdf.zfill(4)}.pdf",
                                    "application/pdf",
                                    key="dl_pdf_reg_indiv",
                                    use_container_width=True,
                                )
                            except Exception as e:
                                st.error(f"❌ {e}")
                        else:
                            st.error("Copropriétaire non trouvé")

                with col4:
                    # ZIP tous les PDFs
                    if st.button("📦 Tous les PDFs (ZIP)", key="btn_pdf_reg_all",
                                 use_container_width=True):
                        import zipfile, io as _io
                        zip_buf = _io.BytesIO()
                        nb_gen = 0
                        errors = []
                        with st.spinner("Génération des PDFs…"):
                            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for _, cop_row_pdf in copro_df.iterrows():
                                    try:
                                        pdf_b = generate_regularisation_pdf_bytes(
                                            SYNDIC_INFO,
                                            cop_row_pdf.to_dict(),
                                            annee_reg,
                                            budgets_appel,
                                            dep_reel_type,
                                            alur_annuel_reg,
                                            nb_appels_reg,
                                        )
                                        lot_pdf = str(cop_row_pdf.get('lot', ''))
                                        zf.writestr(
                                            f"regularisation_{annee_reg}_lot{lot_pdf.zfill(4)}.pdf",
                                            pdf_b
                                        )
                                        nb_gen += 1
                                    except Exception as e_pdf:
                                        errors.append(f"lot {cop_row_pdf.get('lot','?')}: {e_pdf}")
                        zip_buf.seek(0)
                        if errors:
                            st.warning(f"⚠️ {len(errors)} erreur(s) : {'; '.join(errors[:3])}")
                        st.success(f"✅ {nb_gen} PDFs générés")
                        st.download_button(
                            f"⬇️ ZIP ({nb_gen} PDFs)",
                            zip_buf.getvalue(),
                            f"regularisation_{annee_reg}.zip",
                            "application/zip",
                            key="dl_zip_reg_all",
                            use_container_width=True,
                        )

    # ==================== ONGLET 3 : VUE GLOBALE ====================
    with tab3:
        st.subheader("📊 Vue globale annuelle — Charges + Alur par copropriétaire")

        col1, col2, col3 = st.columns(3)
        with col1:
            annee_glob = st.selectbox("📅 Année", annees_bud, key="glob_annee")
        with col2:
            nb_appels_glob = st.selectbox("Nb appels / an", [4,3,2,1], key="glob_nb")
        with col3:
            alur_taux_glob = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_glob")

        bud_glob = budget_df[budget_df['annee'] == annee_glob] if not budget_df.empty else pd.DataFrame()
        total_bud_glob = float(bud_glob['montant_budget'].sum()) if not bud_glob.empty else 0
        alur_glob_annuel = round(total_bud_glob * alur_taux_glob / 100, 2)
        alur_glob_appel = round(alur_glob_annuel / nb_appels_glob, 2)

        st.info(f"Budget {annee_glob} : **{total_bud_glob:,.0f} €** "
                f"+ 🏛️ Alur ({alur_taux_glob:.0f}%) : **{alur_glob_annuel:,.0f} €/an** "
                f"= **{total_bud_glob + alur_glob_annuel:,.0f} €** total | {len(copro_df)} copropriétaires")
        st.divider()

        # Montants auto depuis budget
        montants_glob_auto = {}
        for key, cfg in CHARGES_CONFIG.items():
            if not bud_glob.empty:
                montants_glob_auto[key] = float(bud_glob[bud_glob['classe'].isin(cfg['classes'])]['montant_budget'].sum())
            else:
                montants_glob_auto[key] = 0

        st.subheader("⚙️ Ventilation du budget par type de charge")
        col1, col2, col3 = st.columns(3)
        montants_glob = {}
        for i, (key, cfg) in enumerate(CHARGES_CONFIG.items()):
            col = [col1, col2, col3][i % 3]
            with col:
                montants_glob[key] = st.number_input(
                    f"{cfg['emoji']} {cfg['label']} (€)",
                    min_value=0, value=int(montants_glob_auto.get(key, 0)),
                    step=100, key=f"glob_{key}"
                )

        total_glob = sum(montants_glob.values())
        st.divider()

        glob_df = calculer_appels(copro_df, montants_glob)

        # Alur par copropriétaire via tantième général
        glob_df['🏛️ Alur Annuel (€)'] = (glob_df['_tantieme_general'] / 10000 * alur_glob_annuel).round(2)
        glob_df['💰 TOTAL + Alur Annuel (€)'] = (glob_df['💰 TOTAL Annuel (€)'] + glob_df['🏛️ Alur Annuel (€)']).round(2)

        # Colonnes par appel
        for t in ['T1','T2','T3','T4']:
            glob_df[f'Charges {t} (€)'] = (glob_df['💰 TOTAL Annuel (€)'] / nb_appels_glob).round(2)
            glob_df[f'Alur {t} (€)'] = (glob_df['_tantieme_general'] / 10000 * alur_glob_appel).round(2)
            glob_df[f'🎯 TOTAL {t} (€)'] = (glob_df[f'Charges {t} (€)'] + glob_df[f'Alur {t} (€)']).round(2)

        # Supprimer colonne technique
        if '_tantieme_general' in glob_df.columns:
            glob_df = glob_df.drop(columns=['_tantieme_general'])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget charges", f"{total_glob:,.0f} €")
        c2.metric(f"🏛️ Alur ({alur_taux_glob:.0f}%)", f"{alur_glob_annuel:,.0f} €")
        c3.metric("💰 TOTAL annuel + Alur", f"{glob_df['💰 TOTAL + Alur Annuel (€)'].sum():,.2f} €")
        c4.metric("Appel moyen / copro", f"{glob_df['💰 TOTAL + Alur Annuel (€)'].mean():,.2f} €")

        st.divider()

        # Choix de vue
        vue = st.radio("Affichage", ["Vue annuelle", "Vue par appel (T1/T2/T3/T4)"], horizontal=True, key="glob_vue")

        if vue == "Vue annuelle":
            display_cols = ['Lot','Copropriétaire','Étage','Usage',
                            '💰 TOTAL Annuel (€)','🏛️ Alur Annuel (€)','💰 TOTAL + Alur Annuel (€)']
        else:
            display_cols = ['Lot','Copropriétaire','Étage','Usage']
            for t in ['T1','T2','T3','T4']:
                display_cols += [f'Charges {t} (€)', f'Alur {t} (€)', f'🎯 TOTAL {t} (€)']

        display_cols = [c for c in display_cols if c in glob_df.columns]
        st.dataframe(glob_df[display_cols], use_container_width=True, hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%.2f") for c in display_cols if '€' in c})

        fig = px.bar(
            glob_df.sort_values('💰 TOTAL + Alur Annuel (€)', ascending=False),
            x='Copropriétaire', y=['💰 TOTAL Annuel (€)', '🏛️ Alur Annuel (€)'],
            title=f"Charges annuelles + Alur {annee_glob} par copropriétaire",
            labels={'value': 'Montant (€)', 'variable': 'Type'},
            color_discrete_map={'💰 TOTAL Annuel (€)': '#1f77b4', '🏛️ Alur Annuel (€)': '#ff7f0e'},
            barmode='stack'
        )
        fig.update_layout(xaxis_tickangle=45, height=500)
        st.plotly_chart(fig, use_container_width=True)

        csv_glob = glob_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button(f"📥 Exporter vue globale {annee_glob} (avec Alur)",
            csv_glob, f"charges_{annee_glob}.csv", "text/csv")

# ==================== ANALYSES ====================
elif menu == "🏛️ Loi Alur":
    st.markdown("<h1 class='main-header'>🏛️ Suivi Loi Alur — Fonds de Travaux</h1>", unsafe_allow_html=True)

    alur_df = get_loi_alur()
    depenses_df_alur = get_depenses()

    # Préparer les dépenses
    if not depenses_df_alur.empty:
        depenses_df_alur['date'] = pd.to_datetime(depenses_df_alur['date'])
        depenses_df_alur['montant_du'] = pd.to_numeric(depenses_df_alur['montant_du'], errors='coerce').fillna(0)

    # IDs dépenses déjà affectées Alur
    alur_depense_ids = get_depenses_alur_ids()

    # ---- MÉTRIQUES GLOBALES ----
    if not alur_df.empty:
        alur_df['date'] = pd.to_datetime(alur_df['date'])
        alur_df['appels_fonds'] = pd.to_numeric(alur_df['appels_fonds'], errors='coerce').fillna(0)
        alur_df['utilisation'] = pd.to_numeric(alur_df['utilisation'], errors='coerce').fillna(0)
        if 'commentaire' in alur_df.columns:
            alur_df['commentaire'] = alur_df['commentaire'].fillna('').astype(str).replace('None', '')
        total_appels = alur_df['appels_fonds'].sum()
        total_util = alur_df['utilisation'].sum()
        solde = total_appels - total_util
    else:
        total_appels = total_util = solde = 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total appelé", f"{total_appels:,.2f} €")
    c2.metric("🔧 Total utilisé", f"{total_util:,.2f} €")
    c3.metric("📊 Solde disponible", f"{solde:,.2f} €",
        delta_color="normal" if solde >= 0 else "inverse")
    c4.metric("Nb opérations", len(alur_df) if not alur_df.empty else 0)

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Grand Livre", "➕ Ajouter opération", "🔗 Affecter dépenses", "📊 Analyse"
    ])

    # ---- ONGLET 1 : GRAND LIVRE ----
    with tab1:
        st.subheader("Grand Livre du Fonds de Travaux")
        if alur_df.empty:
            st.info("💡 Aucune opération. Commencez par ajouter un 'À nouveau' ou un appel de fonds.")
        else:
            # Calcul du solde cumulé
            alur_display = alur_df.copy().sort_values('date')
            alur_display['Solde cumulé (€)'] = (alur_display['appels_fonds'] - alur_display['utilisation']).cumsum().round(2)
            alur_display['date_fmt'] = alur_display['date'].dt.strftime('%d/%m/%Y')
            # Masquer les 0 : afficher vide si valeur = 0
            alur_display['Appels (€)'] = alur_display['appels_fonds'].apply(
                lambda x: x if x > 0 else None)
            alur_display['Utilisation (€)'] = alur_display['utilisation'].apply(
                lambda x: x if x > 0 else None)
            alur_display['Commentaire'] = alur_display.get('commentaire', pd.Series(['']*len(alur_display))).fillna('').replace('None','')

            cols_display = ['date_fmt','designation','Appels (€)','Utilisation (€)','Commentaire','Solde cumulé (€)']
            cols_display = [c for c in cols_display if c in alur_display.columns]
            st.dataframe(
                alur_display[cols_display].rename(columns={'date_fmt': 'Date', 'designation': 'Désignation'}),
                use_container_width=True, hide_index=True,
                column_config={
                    'Appels (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Utilisation (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Solde cumulé (€)': st.column_config.NumberColumn(format="%,.2f"),
                }
            )

            # Graphique solde cumulé
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Appels', x=alur_display['date_fmt'],
                y=alur_display['appels_fonds'], marker_color='#2ecc71'))
            fig.add_trace(go.Bar(name='Utilisation', x=alur_display['date_fmt'],
                y=-alur_display['utilisation'], marker_color='#e74c3c'))
            fig.add_trace(go.Scatter(name='Solde cumulé', x=alur_display['date_fmt'],
                y=alur_display['Solde cumulé (€)'], mode='lines+markers',
                line=dict(color='orange', width=3), yaxis='y'))
            fig.update_layout(barmode='relative', title="Évolution du fonds de travaux",
                yaxis_title='Montant (€)', height=400)
            st.plotly_chart(fig, use_container_width=True)

            csv_alur = alur_display.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button("📥 Exporter Grand Livre CSV", csv_alur, "grand_livre_alur.csv", "text/csv")

    # ---- ONGLET 2 : AJOUTER OPÉRATION ----
    with tab2:
        st.subheader("Ajouter une opération au fonds")
        type_op = st.radio("Type d'opération",
            ["💰 Appel de fonds", "🔧 Utilisation / Dépense", "📋 À nouveau"],
            horizontal=True, key="alur_type_op")

        with st.form("form_alur"):
            col1, col2 = st.columns(2)
            with col1:
                op_date = st.date_input("Date *", value=datetime.now())
                op_desig = st.text_input("Désignation *",
                    placeholder="Ex: Appel de fonds T1 2026, Travaux toiture...")
            with col2:
                if type_op == "💰 Appel de fonds":
                    op_appel = st.number_input("Montant appelé (€) *", min_value=0.0, step=100.0, format="%.2f")
                    op_util = 0.0
                elif type_op == "🔧 Utilisation / Dépense":
                    op_appel = 0.0
                    op_util = st.number_input("Montant utilisé (€) *", min_value=0.0, step=100.0, format="%.2f")
                else:  # À nouveau
                    op_appel = st.number_input("Solde reporté (€) *", min_value=0.0, step=100.0, format="%.2f")
                    op_util = 0.0
                op_comment = st.text_area("Commentaire")

            if st.form_submit_button("✨ Enregistrer", type="primary", use_container_width=True):
                if op_desig and (op_appel > 0 or op_util > 0):
                    try:
                        supabase.table('loi_alur').insert({
                            'date': op_date.strftime('%Y-%m-%d'),
                            'designation': op_desig.strip(),
                            'appels_fonds': float(op_appel) if op_appel > 0 else None,
                            'utilisation': float(op_util) if op_util > 0 else None,
                            'commentaire': op_comment.strip() if op_comment else None,
                            'depense_id': None
                        }).execute()
                        st.success("✅ Opération enregistrée!"); st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
                else:
                    st.error("❌ Remplissez tous les champs obligatoires")

        # Suppression
        st.divider()
        st.subheader("🗑️ Supprimer une opération")
        if not alur_df.empty:
            alur_no_dep = alur_df[alur_df.get('depense_id', pd.Series([None]*len(alur_df))).isna()]
            if not alur_no_dep.empty:
                ids_del = st.multiselect("Sélectionner",
                    options=alur_no_dep['id'].tolist(),
                    format_func=lambda x: f"{alur_no_dep[alur_no_dep['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — {alur_no_dep[alur_no_dep['id']==x]['designation'].values[0]}")
                if ids_del and st.button("🗑️ Supprimer", type="secondary"):
                    for i in ids_del: supabase.table('loi_alur').delete().eq('id', i).execute()
                    st.success(f"✅ {len(ids_del)} supprimé(s)"); st.rerun()

    # ---- ONGLET 3 : AFFECTER DÉPENSES ----
    with tab3:
        st.subheader("🔗 Affecter des dépenses au fonds Alur")
        st.info("""
        Certaines dépenses de la table **Dépenses** peuvent être financées par le fonds de travaux Alur.
        En les affectant ici, elles seront **exclues du 5ème appel de charges courantes**
        et comptabilisées dans le fonds Alur.
        """)

        if depenses_df_alur.empty:
            st.warning("⚠️ Aucune dépense disponible.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                annee_aff = st.selectbox("📅 Année", sorted(depenses_df_alur['date'].dt.year.unique(), reverse=True), key="alur_aff_annee")
            with col2:
                show_already = st.checkbox("Afficher les dépenses déjà affectées", value=False)

            dep_annee = depenses_df_alur[depenses_df_alur['date'].dt.year == annee_aff].copy()

            # Marquer les dépenses déjà affectées
            dep_annee['alur'] = dep_annee['id'].isin(alur_depense_ids)

            if not show_already:
                dep_non_affectees = dep_annee[~dep_annee['alur']]
            else:
                dep_non_affectees = dep_annee

            st.write(f"**{len(dep_annee[~dep_annee['alur']])}** dépenses non affectées | "
                     f"**{len(dep_annee[dep_annee['alur']])}** déjà affectées au fonds Alur")

            if not dep_non_affectees.empty:
                ids_select = st.multiselect(
                    "Sélectionner les dépenses à affecter au fonds Alur",
                    options=dep_non_affectees[~dep_non_affectees['alur']]['id'].tolist() if not show_already else [],
                    format_func=lambda x: (
                        f"{dep_non_affectees[dep_non_affectees['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                        f"{dep_non_affectees[dep_non_affectees['id']==x]['fournisseur'].values[0]} — "
                        f"{dep_non_affectees[dep_non_affectees['id']==x]['montant_du'].values[0]:,.2f} €"
                    ),
                    key="alur_dep_select"
                )

                # Tableau récapitulatif
                disp_dep = dep_non_affectees[['date','compte','fournisseur','montant_du','classe','commentaire']].copy()
                disp_dep['date'] = disp_dep['date'].dt.strftime('%d/%m/%Y')
                disp_dep['Alur'] = dep_non_affectees['alur'].map({True: '✅ Affectée', False: '—'})
                st.dataframe(disp_dep, use_container_width=True, hide_index=True,
                    column_config={"montant_du": st.column_config.NumberColumn("Montant (€)", format="%,.2f")})

                if ids_select:
                    total_sel = dep_non_affectees[dep_non_affectees['id'].isin(ids_select)]['montant_du'].sum()
                    st.info(f"**{len(ids_select)}** dépense(s) sélectionnée(s) — Total : **{total_sel:,.2f} €**")

                    col1, col2 = st.columns(2)
                    with col1:
                        desig_alur = st.text_input("Désignation dans le fonds Alur",
                            value=f"Dépenses affectées Alur {annee_aff}", key="alur_desig_aff")
                    with col2:
                        comment_alur = st.text_area("Commentaire", key="alur_comment_aff")

                    if st.button("🔗 Affecter au fonds Alur", type="primary"):
                        try:
                            for dep_id in ids_select:
                                dep_row = dep_non_affectees[dep_non_affectees['id'] == dep_id].iloc[0]
                                supabase.table('loi_alur').insert({
                                    'date': dep_row['date'].strftime('%Y-%m-%d') if hasattr(dep_row['date'], 'strftime') else str(dep_row['date']),
                                    'designation': f"{dep_row['fournisseur']} — {dep_row.get('commentaire','') or desig_alur}",
                                    'appels_fonds': None,
                                    'utilisation': float(dep_row['montant_du']),
                                    'commentaire': comment_alur.strip() if comment_alur else None,
                                    'depense_id': int(dep_id)
                                }).execute()
                            st.success(f"✅ {len(ids_select)} dépense(s) affectée(s) au fonds Alur!"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

            # Désaffecter
            st.divider()
            st.subheader("↩️ Désaffecter des dépenses")
            dep_affectees = dep_annee[dep_annee['alur']]
            if not dep_affectees.empty:
                ids_desaff = st.multiselect("Dépenses à désaffecter",
                    options=dep_affectees['id'].tolist(),
                    format_func=lambda x: (
                        f"{dep_affectees[dep_affectees['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                        f"{dep_affectees[dep_affectees['id']==x]['fournisseur'].values[0]} — "
                        f"{dep_affectees[dep_affectees['id']==x]['montant_du'].values[0]:,.2f} €"
                    ), key="alur_desaff")
                if ids_desaff and st.button("↩️ Désaffecter", type="secondary"):
                    try:
                        for dep_id in ids_desaff:
                            supabase.table('loi_alur').delete().eq('depense_id', dep_id).execute()
                        st.success(f"✅ {len(ids_desaff)} dépense(s) désaffectée(s)"); st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
            else:
                st.info("Aucune dépense affectée pour cette année.")

    # ---- ONGLET 4 : ANALYSE ----
    with tab4:
        st.subheader("📊 Analyse du fonds de travaux")
        if alur_df.empty:
            st.info("Aucune donnée disponible.")
        else:
            alur_an = alur_df.copy()
            alur_an['annee'] = alur_an['date'].dt.year
            by_year = alur_an.groupby('annee').agg(
                appels=('appels_fonds','sum'), util=('utilisation','sum')
            ).reset_index()
            by_year['solde'] = by_year['appels'] - by_year['util']

            col1, col2 = st.columns(2)
            with col1:
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Appels', x=by_year['annee'].astype(str), y=by_year['appels'], marker_color='#2ecc71'))
                fig.add_trace(go.Bar(name='Utilisation', x=by_year['annee'].astype(str), y=by_year['util'], marker_color='#e74c3c'))
                fig.update_layout(barmode='group', title='Appels vs Utilisation par année')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.bar(by_year, x='annee', y='solde', title='Solde net par année',
                    color='solde', color_continuous_scale=['red','green'],
                    text='solde', labels={'solde':'Solde (€)', 'annee':'Année'})
                fig.update_traces(texttemplate='%{text:,.0f}€', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("Impact sur le 5ème appel")
            total_dep_alur = alur_df[alur_df.get('depense_id', pd.Series([None]*len(alur_df))).notna()]['utilisation'].sum()
            if total_dep_alur > 0:
                st.success(f"✅ **{total_dep_alur:,.2f} €** de dépenses affectées au fonds Alur "
                           f"sont exclues du 5ème appel de charges courantes.")
            else:
                st.info("Aucune dépense n'est encore affectée au fonds Alur.")

elif menu == "📈 Analyses":
    st.markdown("<h1 class='main-header'>📈 Analyses Avancées</h1>", unsafe_allow_html=True)
    depenses_df = get_depenses()
    budget_df = get_budget()

    if not depenses_df.empty and not budget_df.empty:
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df['annee'] = depenses_df['date'].dt.year
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')

        annees = sorted(depenses_df['annee'].unique(), reverse=True)
        annee_a = st.selectbox("📅 Année", annees, key="anal_annee")
        dep_a = depenses_df[depenses_df['annee'] == annee_a].copy()
        bud_a = budget_df[budget_df['annee'] == annee_a].copy()

        st.divider()
        st.subheader(f"📊 Analyse Budget vs Réalisé par Classe — {annee_a}")

        classes_labels = {
            '1A':'Charges courantes', '1B':'Entretien courant', '2':'Élec. RDC/ss-sols',
            '3':'Élec. sous-sols', '4':'Garages/Parkings', '5':'Ascenseurs',
            '6':'Monte-voitures', '7':'Travaux/Divers'
        }
        rows = []
        tot_bud = 0; tot_dep = 0
        for cl, lib in classes_labels.items():
            b = float(bud_a[bud_a['classe']==cl]['montant_budget'].sum()) if 'classe' in bud_a.columns else 0
            d = float(dep_a[dep_a['classe']==cl]['montant_du'].sum()) if 'classe' in dep_a.columns else 0
            rows.append({'Classe': cl, 'Libellé': lib, 'Budget (€)': b, 'Dépenses (€)': d,
                         'Écart (€)': b-d, '% Réalisé': round(d/b*100,1) if b > 0 else 0})
            tot_bud += b; tot_dep += d
        rows.append({'Classe':'TOTAL','Libellé':'','Budget (€)':tot_bud,'Dépenses (€)':tot_dep,
                     'Écart (€)':tot_bud-tot_dep,'% Réalisé':round(tot_dep/tot_bud*100,1) if tot_bud>0 else 0})

        anal_df = pd.DataFrame(rows)
        st.dataframe(anal_df, use_container_width=True, hide_index=True,
            column_config={
                "Budget (€)": st.column_config.NumberColumn(format="%,.0f"),
                "Dépenses (€)": st.column_config.NumberColumn(format="%,.2f"),
                "Écart (€)": st.column_config.NumberColumn(format="%,.2f"),
                "% Réalisé": st.column_config.NumberColumn(format="%.1f%%"),
            })

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Budget vs Dépenses par Classe")
            fig = go.Figure()
            df_no_total = anal_df[anal_df['Classe'] != 'TOTAL']
            fig.add_trace(go.Bar(name='Budget', x=df_no_total['Classe'], y=df_no_total['Budget (€)'], marker_color='lightblue'))
            fig.add_trace(go.Bar(name='Dépenses', x=df_no_total['Classe'], y=df_no_total['Dépenses (€)'], marker_color='salmon'))
            fig.update_layout(barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Top Fournisseurs")
            if not dep_a.empty and 'fournisseur' in dep_a.columns:
                top_f = dep_a.groupby('fournisseur')['montant_du'].agg(['sum','count']).reset_index()
                top_f.columns = ['Fournisseur','Total (€)','Nb factures']
                top_f = top_f.sort_values('Total (€)', ascending=False).head(10)
                fig = px.bar(top_f, x='Fournisseur', y='Total (€)', color='Nb factures', text='Total (€)')
                fig.update_traces(texttemplate='%{text:,.0f}€', textposition='outside')
                fig.update_layout(xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"📅 Évolution Mensuelle — {annee_a}")
        if not dep_a.empty:
            dep_a['mois'] = dep_a['date'].dt.to_period('M').astype(str)
            ev = dep_a.groupby('mois')['montant_du'].sum().reset_index()
            fig = px.area(ev, x='mois', y='montant_du', labels={'montant_du':'Montant (€)','mois':'Mois'},
                title=f"Évolution mensuelle {annee_a}")
            st.plotly_chart(fig, use_container_width=True)

        st.download_button("📥 Exporter l'analyse CSV",
            anal_df.to_csv(index=False).encode('utf-8'), f"analyse_{annee_a}.csv", "text/csv")
    else:
        st.warning("⚠️ Données insuffisantes pour les analyses")

# ==================== PLAN COMPTABLE ====================
elif menu == "📋 Plan Comptable":
    st.markdown("<h1 class='main-header'>📋 Plan Comptable</h1>", unsafe_allow_html=True)
    plan_df = get_plan_comptable()

    pc_tab1, pc_tab2, pc_tab3, pc_tab4 = st.tabs(["📋 Consulter", "➕ Ajouter", "✏️ Modifier", "🗑️ Supprimer"])

    # ── ONGLET CONSULTER ─────────────────────────────────────────
    with pc_tab1:
        if not plan_df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Comptes", len(plan_df))
            c2.metric("Classes", plan_df['classe'].nunique() if 'classe' in plan_df.columns else "N/A")
            c3.metric("Familles", plan_df['famille'].nunique() if 'famille' in plan_df.columns else "N/A")
            st.divider()

            col1, col2, col3 = st.columns(3)
            with col1:
                cl_f = st.selectbox("Classe", ['Toutes'] + sorted(plan_df['classe'].dropna().unique().tolist()), key="pc_cl_f")
            with col2:
                fam_f = st.selectbox("Famille", ['Toutes'] + sorted(plan_df['famille'].dropna().unique().tolist()), key="pc_fam_f")
            with col3:
                search = st.text_input("🔍 Recherche", key="pc_search")

            filt = plan_df.copy()
            if cl_f != 'Toutes': filt = filt[filt['classe'] == cl_f]
            if fam_f != 'Toutes': filt = filt[filt['famille'] == fam_f]
            if search:
                mask = filt['compte'].astype(str).str.contains(search, case=False, na=False)
                if 'libelle_compte' in filt.columns:
                    mask |= filt['libelle_compte'].astype(str).str.contains(search, case=False, na=False)
                filt = filt[mask]

            disp_cols = [c for c in ['compte','libelle_compte','classe','famille'] if c in filt.columns]
            st.dataframe(
                filt[disp_cols].sort_values('compte' if 'compte' in filt.columns else disp_cols[0]),
                use_container_width=True, hide_index=True
            )
            st.download_button("📥 Exporter CSV",
                filt.to_csv(index=False).encode('utf-8'),
                f"plan_comptable_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

            col1, col2 = st.columns(2)
            with col1:
                if 'classe' in filt.columns:
                    cl_cnt = filt['classe'].value_counts().reset_index()
                    cl_cnt.columns = ['Classe','Nb comptes']
                    fig = px.bar(cl_cnt, x='Classe', y='Nb comptes', title='Comptes par classe', text='Nb comptes')
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                if 'famille' in filt.columns:
                    fam_cnt = filt['famille'].value_counts().reset_index()
                    fam_cnt.columns = ['Famille','Nb comptes']
                    fig = px.pie(fam_cnt, values='Nb comptes', names='Famille', title='Comptes par famille')
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ Aucune donnée dans le plan comptable.")

    # ── ONGLET AJOUTER ───────────────────────────────────────────
    with pc_tab2:
        st.subheader("➕ Ajouter un compte")
        classes_ex  = sorted(plan_df['classe'].dropna().unique().tolist()) if not plan_df.empty else []
        familles_ex = sorted(plan_df['famille'].dropna().unique().tolist()) if not plan_df.empty else []

        with st.form("form_add_pc"):
            col1, col2 = st.columns(2)
            with col1:
                new_compte   = st.text_input("Numéro de compte *", placeholder="ex: 60201500")
                new_libelle  = st.text_input("Libellé *", placeholder="ex: EAU FROIDE GENERALE")
            with col2:
                # Classe : existante ou nouvelle
                use_new_cl = st.checkbox("Nouvelle classe", key="new_cl_chk")
                if use_new_cl:
                    new_classe = st.text_input("Nouvelle classe *", placeholder="ex: 1C")
                else:
                    new_classe = st.selectbox("Classe *", classes_ex, key="pc_add_cl")
                # Famille : existante ou nouvelle
                use_new_fam = st.checkbox("Nouvelle famille", key="new_fam_chk")
                if use_new_fam:
                    new_famille = st.text_input("Nouvelle famille *", placeholder="ex: 6025")
                else:
                    new_famille = st.selectbox("Famille *", familles_ex, key="pc_add_fam")

            submitted_add = st.form_submit_button("✅ Ajouter le compte", use_container_width=True)
            if submitted_add:
                if not new_compte or not new_libelle or not new_classe or not new_famille:
                    st.error("⚠️ Tous les champs marqués * sont obligatoires.")
                elif not plan_df.empty and new_compte in plan_df['compte'].astype(str).values:
                    st.error(f"⚠️ Le compte **{new_compte}** existe déjà.")
                else:
                    try:
                        supabase.table('plan_comptable').insert({
                            'compte':        new_compte,
                            'libelle_compte': new_libelle.upper().strip(),
                            'classe':        new_classe.strip(),
                            'famille':       new_famille.strip(),
                        }).execute()
                        st.success(f"✅ Compte **{new_compte} — {new_libelle.upper()}** ajouté.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")

    # ── ONGLET MODIFIER ──────────────────────────────────────────
    with pc_tab3:
        st.subheader("✏️ Modifier un compte")
        if plan_df.empty:
            st.warning("⚠️ Aucun compte disponible.")
        else:
            mod_tab1, mod_tab2, mod_tab3 = st.tabs(["📝 Compte individuel", "🏷️ Renommer une classe", "📁 Renommer une famille"])

            # ── Modifier un compte individuel
            with mod_tab1:
                choix_comptes = plan_df.apply(
                    lambda r: f"{r['compte']} — {r['libelle_compte']} ({r['classe']})", axis=1
                ).tolist()
                sel_compte = st.selectbox("Sélectionner le compte à modifier", choix_comptes, key="pc_mod_sel")
                sel_id = int(plan_df.iloc[choix_comptes.index(sel_compte)]['id'])
                sel_row = plan_df[plan_df['id'] == sel_id].iloc[0]

                with st.form("form_mod_pc"):
                    col1, col2 = st.columns(2)
                    with col1:
                        mod_compte  = st.text_input("Numéro de compte", value=str(sel_row['compte']))
                        mod_libelle = st.text_input("Libellé", value=str(sel_row['libelle_compte']))
                    with col2:
                        classes_mod = sorted(plan_df['classe'].dropna().unique().tolist())
                        idx_cl = classes_mod.index(sel_row['classe']) if sel_row['classe'] in classes_mod else 0
                        mod_classe  = st.selectbox("Classe", classes_mod, index=idx_cl, key="pc_mod_cl")
                        familles_mod = sorted(plan_df['famille'].dropna().unique().tolist())
                        idx_fam = familles_mod.index(sel_row['famille']) if sel_row['famille'] in familles_mod else 0
                        mod_famille = st.selectbox("Famille", familles_mod, index=idx_fam, key="pc_mod_fam")

                    submitted_mod = st.form_submit_button("💾 Enregistrer les modifications", use_container_width=True)
                    if submitted_mod:
                        try:
                            supabase.table('plan_comptable').update({
                                'compte':        mod_compte.strip(),
                                'libelle_compte': mod_libelle.upper().strip(),
                                'classe':        mod_classe.strip(),
                                'famille':       mod_famille.strip(),
                            }).eq('id', sel_id).execute()
                            st.success(f"✅ Compte **{mod_compte}** mis à jour.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur : {e}")

            # ── Renommer une classe (tous les comptes de la classe)
            with mod_tab2:
                st.info("ℹ️ Renomme la classe sur **tous les comptes** qui l'utilisent.")
                classes_list = sorted(plan_df['classe'].dropna().unique().tolist())
                col1, col2 = st.columns(2)
                with col1:
                    cl_ancien = st.selectbox("Classe à renommer", classes_list, key="cl_rename_old")
                    nb_cl = len(plan_df[plan_df['classe'] == cl_ancien])
                    st.caption(f"{nb_cl} compte(s) affectés")
                with col2:
                    cl_nouveau = st.text_input("Nouveau nom de classe", key="cl_rename_new")
                if st.button("✏️ Renommer la classe", key="btn_rename_cl", use_container_width=True):
                    if not cl_nouveau.strip():
                        st.error("⚠️ Saisir le nouveau nom.")
                    elif cl_nouveau.strip() in classes_list and cl_nouveau.strip() != cl_ancien:
                        st.error(f"⚠️ La classe **{cl_nouveau}** existe déjà.")
                    else:
                        try:
                            supabase.table('plan_comptable').update({'classe': cl_nouveau.strip()}).eq('classe', cl_ancien).execute()
                            st.success(f"✅ Classe **{cl_ancien}** → **{cl_nouveau}** ({nb_cl} comptes mis à jour).")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

            # ── Renommer une famille
            with mod_tab3:
                st.info("ℹ️ Renomme la famille sur **tous les comptes** qui l'utilisent.")
                familles_list = sorted(plan_df['famille'].dropna().unique().tolist())
                col1, col2 = st.columns(2)
                with col1:
                    fam_ancien = st.selectbox("Famille à renommer", familles_list, key="fam_rename_old")
                    nb_fam = len(plan_df[plan_df['famille'] == fam_ancien])
                    st.caption(f"{nb_fam} compte(s) affectés")
                with col2:
                    fam_nouveau = st.text_input("Nouveau nom de famille", key="fam_rename_new")
                if st.button("✏️ Renommer la famille", key="btn_rename_fam", use_container_width=True):
                    if not fam_nouveau.strip():
                        st.error("⚠️ Saisir le nouveau nom.")
                    elif fam_nouveau.strip() in familles_list and fam_nouveau.strip() != fam_ancien:
                        st.error(f"⚠️ La famille **{fam_nouveau}** existe déjà.")
                    else:
                        try:
                            supabase.table('plan_comptable').update({'famille': fam_nouveau.strip()}).eq('famille', fam_ancien).execute()
                            st.success(f"✅ Famille **{fam_ancien}** → **{fam_nouveau}** ({nb_fam} comptes mis à jour).")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

    # ── ONGLET SUPPRIMER ─────────────────────────────────────────
    with pc_tab4:
        st.subheader("🗑️ Supprimer")
        if plan_df.empty:
            st.warning("⚠️ Aucun compte disponible.")
        else:
            del_tab1, del_tab2, del_tab3 = st.tabs(["🗑️ Un compte", "🗑️ Une classe entière", "🗑️ Une famille entière"])

            # ── Supprimer un compte
            with del_tab1:
                del_comptes = plan_df.apply(
                    lambda r: f"{r['compte']} — {r['libelle_compte']} ({r['classe']})", axis=1
                ).tolist()
                sel_del = st.selectbox("Compte à supprimer", del_comptes, key="pc_del_sel")
                sel_del_id  = int(plan_df.iloc[del_comptes.index(sel_del)]['id'])
                sel_del_row = plan_df[plan_df['id'] == sel_del_id].iloc[0]

                st.warning(f"⚠️ Supprimer **{sel_del_row['compte']} — {sel_del_row['libelle_compte']}** ?  "
                           f"Cette action est irréversible.")
                col1, col2 = st.columns(2)
                with col1:
                    confirm_del = st.checkbox("Je confirme la suppression", key="chk_del_pc")
                with col2:
                    if st.button("🗑️ Supprimer ce compte", key="btn_del_pc",
                                 disabled=not confirm_del, use_container_width=True):
                        try:
                            supabase.table('plan_comptable').delete().eq('id', sel_del_id).execute()
                            st.success(f"✅ Compte **{sel_del_row['compte']}** supprimé.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

            # ── Supprimer une classe entière
            with del_tab2:
                classes_del = sorted(plan_df['classe'].dropna().unique().tolist())
                cl_del = st.selectbox("Classe à supprimer", classes_del, key="cl_del_sel")
                nb_cl_del = len(plan_df[plan_df['classe'] == cl_del])
                comptes_cl = plan_df[plan_df['classe'] == cl_del]['compte'].astype(str).tolist()
                st.warning(f"⚠️ Supprimer la classe **{cl_del}** et ses **{nb_cl_del} comptes** : "
                           f"{', '.join(comptes_cl[:8])}{'...' if len(comptes_cl) > 8 else ''} ?")
                col1, col2 = st.columns(2)
                with col1:
                    confirm_cl_del = st.checkbox("Je confirme la suppression de la classe", key="chk_del_cl")
                with col2:
                    if st.button(f"🗑️ Supprimer classe {cl_del} ({nb_cl_del} comptes)",
                                 key="btn_del_cl", disabled=not confirm_cl_del, use_container_width=True):
                        try:
                            supabase.table('plan_comptable').delete().eq('classe', cl_del).execute()
                            st.success(f"✅ Classe **{cl_del}** et {nb_cl_del} comptes supprimés.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

            # ── Supprimer une famille entière
            with del_tab3:
                familles_del = sorted(plan_df['famille'].dropna().unique().tolist())
                fam_del = st.selectbox("Famille à supprimer", familles_del, key="fam_del_sel")
                nb_fam_del = len(plan_df[plan_df['famille'] == fam_del])
                comptes_fam = plan_df[plan_df['famille'] == fam_del]['compte'].astype(str).tolist()
                st.warning(f"⚠️ Supprimer la famille **{fam_del}** et ses **{nb_fam_del} comptes** : "
                           f"{', '.join(comptes_fam[:8])}{'...' if len(comptes_fam) > 8 else ''} ?")
                col1, col2 = st.columns(2)
                with col1:
                    confirm_fam_del = st.checkbox("Je confirme la suppression de la famille", key="chk_del_fam")
                with col2:
                    if st.button(f"🗑️ Supprimer famille {fam_del} ({nb_fam_del} comptes)",
                                 key="btn_del_fam", disabled=not confirm_fam_del, use_container_width=True):
                        try:
                            supabase.table('plan_comptable').delete().eq('famille', fam_del).execute()
                            st.success(f"✅ Famille **{fam_del}** et {nb_fam_del} comptes supprimés.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

# ==================== ONGLET AG ====================
elif menu == "🏛 AG — Assemblée Générale":
    st.markdown("<h1 class='main-header'>🏛 Assemblée Générale</h1>", unsafe_allow_html=True)

    # Fonction pour charger les AG depuis Supabase
    @st.cache_data(ttl=30)
    def get_ag_list():
        try:
            r = supabase.table('ag').select('*').order('date', desc=True).execute()
            return pd.DataFrame(r.data) if r.data else pd.DataFrame()
        except:
            return pd.DataFrame()

    @st.cache_data(ttl=30)
    def get_ag_items(ag_id):
        try:
            r = supabase.table('ag_items').select('*').eq('ag_id', ag_id).order('ordre').execute()
            return pd.DataFrame(r.data) if r.data else pd.DataFrame()
        except:
            return pd.DataFrame()

    @st.cache_data(ttl=30)
    def get_ag_docs(ag_id):
        try:
            r = supabase.table('ag_documents').select('*').eq('ag_id', ag_id).order('created_at').execute()
            return pd.DataFrame(r.data) if r.data else pd.DataFrame()
        except:
            return pd.DataFrame()

    def upload_ag_doc(ag_id, file_bytes, filename):
        import uuid as _uuid
        ext  = filename.rsplit('.', 1)[-1].lower()
        safe = filename.replace(' ', '_')
        path = f"ag/{ag_id}/{_uuid.uuid4().hex[:8]}_{safe}"
        ctype_map = {
            'pdf':'application/pdf','jpg':'image/jpeg','jpeg':'image/jpeg',
            'png':'image/png','mp4':'video/mp4','mov':'video/quicktime',
            'avi':'video/x-msvideo','doc':'application/msword',
            'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls':'application/vnd.ms-excel',
            'xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        ctype = ctype_map.get(ext, 'application/octet-stream')
        supabase.storage.from_('factures').upload(path, file_bytes,
            file_options={"content-type": ctype, "upsert": "true"})
        return path

    ag_tab1, ag_tab2, ag_tab3, ag_tab4 = st.tabs(["📋 Consulter / Répondre", "📎 Documents", "➕ Nouvelle AG", "🗑️ Gérer"])

    # ── ONGLET CONSULTER ────────────────────────────────────────
    with ag_tab1:
        ag_df = get_ag_list()

        if ag_df.empty:
            st.info("Aucune AG enregistrée. Créez-en une dans l'onglet **➕ Nouvelle AG**.")
        else:
            # Sélection de l'AG
            ag_options = ag_df.apply(
                lambda r: f"{r['date']} — {r['titre']}", axis=1
            ).tolist()
            sel_ag_label = st.selectbox("📅 Assemblée Générale", ag_options, key="ag_sel")
            sel_ag_idx = ag_options.index(sel_ag_label)
            sel_ag = ag_df.iloc[sel_ag_idx]
            sel_ag_id = int(sel_ag['id'])

            st.divider()
            col_info1, col_info2, col_info3 = st.columns(3)
            col_info1.metric("Date", sel_ag['date'])
            col_info2.metric("Lieu", sel_ag.get('lieu', '—') or '—')
            col_info3.metric("Type", sel_ag.get('type_ag', '—') or '—')
            if sel_ag.get('description'):
                st.caption(sel_ag['description'])

            st.divider()

            items_df = get_ag_items(sel_ag_id)

            # Bouton ajouter une question/résolution
            with st.expander("➕ Ajouter une question / résolution", expanded=False):
                with st.form(f"form_add_item_{sel_ag_id}"):
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        new_ordre = st.number_input("N° ordre du jour", min_value=1,
                            value=int(items_df['ordre'].max() + 1) if not items_df.empty else 1,
                            step=1, key="new_item_ordre")
                        new_type = st.selectbox("Type", ["Question", "Résolution", "Information", "Vote"], key="new_item_type")
                        new_vote = st.selectbox("Vote", ["—", "Approuvé", "Rejeté", "Ajourné", "Sans objet"], key="new_item_vote")
                    with col2:
                        new_titre = st.text_input("Titre / Point de l'ordre du jour *", key="new_item_titre")
                        new_question = st.text_area("Question / Commentaire", height=100, key="new_item_question",
                            placeholder="Texte de la question, de la résolution ou du commentaire...")
                        new_reponse = st.text_area("Réponse / Décision", height=100, key="new_item_reponse",
                            placeholder="Réponse apportée, décision prise, résultat du vote...")
                    submitted_item = st.form_submit_button("✅ Ajouter", use_container_width=True)
                    if submitted_item:
                        if not new_titre:
                            st.error("⚠️ Le titre est obligatoire.")
                        else:
                            try:
                                supabase.table('ag_items').insert({
                                    'ag_id':    sel_ag_id,
                                    'ordre':    int(new_ordre),
                                    'type':     new_type,
                                    'titre':    new_titre.strip(),
                                    'question': new_question.strip() if new_question else None,
                                    'reponse':  new_reponse.strip() if new_reponse else None,
                                    'vote':     new_vote if new_vote != "—" else None,
                                }).execute()
                                st.success("✅ Point ajouté.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

            st.subheader(f"📋 Ordre du jour — {sel_ag['titre']}")

            if items_df.empty:
                st.info("Aucun point à l'ordre du jour. Ajoutez-en un ci-dessus.")
            else:
                VOTE_COLORS = {
                    'Approuvé':   ('#1B5E20', '#E8F5E9'),
                    'Rejeté':     ('#B71C1C', '#FFEBEE'),
                    'Ajourné':    ('#E65100', '#FFF3E0'),
                    'Sans objet': ('#37474F', '#ECEFF1'),
                }
                TYPE_EMOJI = {
                    'Question':    '❓',
                    'Résolution':  '📜',
                    'Information': 'ℹ️',
                    'Vote':        '🗳️',
                }

                for _, item in items_df.sort_values('ordre').iterrows():
                    item_id = int(item['id'])
                    vote = item.get('vote') or ''
                    vote_color, vote_bg = VOTE_COLORS.get(vote, ('#1565C0', '#E3F2FD'))
                    type_emoji = TYPE_EMOJI.get(item.get('type',''), '📌')

                    # Badge vote
                    badge_html = (f"<span style='background:{vote_bg};color:{vote_color};"
                                  f"padding:2px 10px;border-radius:12px;font-size:0.8em;"
                                  f"font-weight:bold;border:1px solid {vote_color};'>{vote}</span>"
                                  if vote else "")

                    st.markdown(
                        f"<div style='background:#1E2130;border-left:4px solid {vote_color};"
                        f"border-radius:6px;padding:10px 14px;margin-bottom:6px;'>"
                        f"<b>{type_emoji} {int(item['ordre'])}. {item['titre']}</b>"
                        f"{'&nbsp;&nbsp;' + badge_html if badge_html else ''}"
                        f"</div>", unsafe_allow_html=True
                    )

                    # Affichage question / réponse en vis-à-vis
                    col_q, col_r = st.columns(2)
                    with col_q:
                        st.markdown("**🗣️ Question / Commentaire**")
                        st.text_area("", value=item.get('question') or '', height=120,
                            disabled=True, key=f"q_ro_{item_id}", label_visibility="collapsed")
                    with col_r:
                        st.markdown("**✅ Réponse / Décision**")
                        reponse_edit = st.text_area("", value=item.get('reponse') or '', height=120,
                            key=f"r_edit_{item_id}", label_visibility="collapsed",
                            placeholder="Saisir la réponse ou décision...")

                    # Ligne d'action : vote + enregistrer + supprimer
                    col_v, col_s, col_del = st.columns([2, 2, 1])
                    with col_v:
                        vote_opts = ["—", "Approuvé", "Rejeté", "Ajourné", "Sans objet"]
                        vote_idx = vote_opts.index(vote) if vote in vote_opts else 0
                        vote_edit = st.selectbox("Vote", vote_opts, index=vote_idx,
                            key=f"vote_{item_id}", label_visibility="collapsed")
                    with col_s:
                        if st.button("💾 Enregistrer", key=f"save_{item_id}", use_container_width=True):
                            try:
                                supabase.table('ag_items').update({
                                    'reponse': reponse_edit.strip() if reponse_edit else None,
                                    'vote':    vote_edit if vote_edit != "—" else None,
                                }).eq('id', item_id).execute()
                                st.success("✅ Enregistré")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")
                    with col_del:
                        if st.button("🗑️", key=f"del_item_{item_id}", use_container_width=True,
                                     help="Supprimer ce point"):
                            try:
                                supabase.table('ag_items').delete().eq('id', item_id).execute()
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

                    st.divider()

            # Export PV
            if not items_df.empty:
                if st.button("📄 Exporter PV (CSV)", key="export_pv"):
                    pv_df = items_df[['ordre','type','titre','question','reponse','vote']].sort_values('ordre')
                    pv_csv = pv_df.to_csv(index=False, sep=';').encode('utf-8-sig')
                    st.download_button("⬇️ Télécharger le PV", pv_csv,
                        f"PV_AG_{sel_ag['date'].replace('/','_')}.csv", "text/csv")

    # ── ONGLET DOCUMENTS ────────────────────────────────────────
    with ag_tab2:
        st.subheader("📎 Documents de l'AG")
        ag_df_doc = get_ag_list()
        if ag_df_doc.empty:
            st.info("Aucune AG. Créez-en une d'abord.")
        else:
            ag_opts_doc = ag_df_doc.apply(lambda r: f"{r['date']} — {r['titre']}", axis=1).tolist()
            sel_ag_doc  = st.selectbox("Sélectionner l'AG", ag_opts_doc, key="ag_doc_sel")
            sel_ag_doc_id = int(ag_df_doc.iloc[ag_opts_doc.index(sel_ag_doc)]['id'])

            docs_df = get_ag_docs(sel_ag_doc_id)

            # ── Upload ──────────────────────────────────────────
            st.markdown("#### 📤 Ajouter un document")
            TYPES_DOCS = ["Devis", "Facture", "Photo / Plan", "Vidéo", "PV / Compte-rendu",
                          "Rapport technique", "Contrat", "Autre"]
            col_up1, col_up2 = st.columns([2,1])
            with col_up1:
                up_files = st.file_uploader(
                    "PDF, images, vidéos, Word, Excel…",
                    type=["pdf","jpg","jpeg","png","gif","webp",
                          "mp4","mov","avi","doc","docx","xls","xlsx"],
                    accept_multiple_files=True,
                    key=f"ag_doc_up_{sel_ag_doc_id}"
                )
            with col_up2:
                up_type    = st.selectbox("Type de document", TYPES_DOCS, key="ag_doc_type")
                up_libelle = st.text_input("Description", placeholder="ex: Devis ascenseur OTIS",
                                           key="ag_doc_lib")

            if up_files:
                if st.button(f"📤 Envoyer {len(up_files)} fichier(s)", type="primary",
                             use_container_width=True, key="btn_ag_doc_up"):
                    nb_ok = 0
                    for f_up in up_files:
                        try:
                            path = upload_ag_doc(sel_ag_doc_id, f_up.read(), f_up.name)
                            supabase.table('ag_documents').insert({
                                'ag_id':      sel_ag_doc_id,
                                'nom':        f_up.name,
                                'type_doc':   up_type,
                                'libelle':    up_libelle.strip() or f_up.name,
                                'storage_path': path,
                                'taille_ko':  round(f_up.size / 1024, 1),
                            }).execute()
                            nb_ok += 1
                        except Exception as e:
                            st.error(f"❌ {f_up.name} — {e}")
                    if nb_ok:
                        st.success(f"✅ {nb_ok} fichier(s) uploadé(s).")
                        st.cache_data.clear(); st.rerun()

            st.divider()

            # ── Liste des documents ──────────────────────────────
            if docs_df.empty:
                st.info("Aucun document pour cette AG.")
            else:
                st.markdown(f"#### 📁 {len(docs_df)} document(s)")

                # Grouper par type
                types_presents = docs_df['type_doc'].dropna().unique() if 'type_doc' in docs_df.columns else ['Autre']
                for doc_type in sorted(types_presents):
                    grp = docs_df[docs_df['type_doc'] == doc_type] if 'type_doc' in docs_df.columns else docs_df
                    st.markdown(f"**{doc_type}** ({len(grp)})")
                    for _, doc in grp.iterrows():
                        doc_path = str(doc.get('storage_path','') or '')
                        doc_nom  = str(doc.get('nom', doc.get('libelle','Fichier')))
                        doc_lib  = str(doc.get('libelle','') or '')
                        doc_ko   = doc.get('taille_ko', 0)
                        doc_id   = int(doc['id'])
                        ext_doc  = doc_nom.rsplit('.',1)[-1].lower() if '.' in doc_nom else ''
                        is_img   = ext_doc in ('jpg','jpeg','png','gif','webp')
                        is_pdf   = ext_doc == 'pdf'
                        is_vid   = ext_doc in ('mp4','mov','avi')

                        with st.expander(
                            f"{'🖼️' if is_img else '🎬' if is_vid else '📄'} "
                            f"{doc_lib or doc_nom}  —  {doc_ko:.0f} Ko",
                            expanded=False
                        ):
                            col_d1, col_d2 = st.columns([2,1])
                            with col_d1:
                                if doc_path:
                                    try:
                                        file_bytes_doc = get_facture_bytes(doc_path)
                                        if file_bytes_doc:
                                            if is_img:
                                                st.image(file_bytes_doc, use_container_width=True)
                                            elif is_pdf:
                                                afficher_facture(doc_path, height=500)
                                            elif is_vid:
                                                st.video(file_bytes_doc)
                                            else:
                                                st.info(f"📄 Fichier {ext_doc.upper()} — utilisez le bouton télécharger")
                                    except Exception as e:
                                        st.warning(f"Aperçu indisponible : {e}")
                            with col_d2:
                                st.markdown(f"**Nom :** {doc_nom}")
                                st.markdown(f"**Type :** {doc_type}")
                                if doc_lib and doc_lib != doc_nom:
                                    st.markdown(f"**Description :** {doc_lib}")
                                st.markdown(f"**Taille :** {doc_ko:.0f} Ko")
                                # Téléchargement
                                if doc_path:
                                    try:
                                        fb = get_facture_bytes(doc_path)
                                        if fb:
                                            mime_map = {'pdf':'application/pdf','jpg':'image/jpeg',
                                                       'jpeg':'image/jpeg','png':'image/png',
                                                       'mp4':'video/mp4','mov':'video/quicktime'}
                                            mime_dl = mime_map.get(ext_doc,'application/octet-stream')
                                            st.download_button("⬇️ Télécharger", data=fb,
                                                file_name=doc_nom, mime=mime_dl,
                                                key=f"dl_agdoc_{doc_id}", use_container_width=True)
                                    except:
                                        pass
                                # Supprimer
                                if st.button("🗑️ Supprimer", key=f"del_agdoc_{doc_id}",
                                             use_container_width=True):
                                    try:
                                        if doc_path:
                                            supabase.storage.from_('factures').remove([doc_path])
                                        supabase.table('ag_documents').delete().eq('id', doc_id).execute()
                                        st.success("✅ Document supprimé.")
                                        st.cache_data.clear(); st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ {e}")

    # ── ONGLET NOUVELLE AG ──────────────────────────────────────
    with ag_tab3:
        st.subheader("➕ Créer une nouvelle Assemblée Générale")
        with st.form("form_new_ag"):
            col1, col2 = st.columns(2)
            with col1:
                ag_date = st.date_input("Date de l'AG *", key="ag_new_date")
                ag_titre = st.text_input("Titre *", placeholder="ex: AG Ordinaire 2025", key="ag_new_titre")
                ag_type = st.selectbox("Type", ["Ordinaire", "Extraordinaire", "Mixte"], key="ag_new_type")
            with col2:
                ag_lieu = st.text_input("Lieu", placeholder="ex: Salle de réunion RDC", key="ag_new_lieu")
                ag_president = st.text_input("Président de séance", key="ag_new_pres")
                ag_desc = st.text_area("Description / Observations", height=100, key="ag_new_desc")
            submitted_ag = st.form_submit_button("✅ Créer l'AG", use_container_width=True)
            if submitted_ag:
                if not ag_titre:
                    st.error("⚠️ Le titre est obligatoire.")
                else:
                    try:
                        supabase.table('ag').insert({
                            'date':       ag_date.strftime('%Y-%m-%d'),
                            'titre':      ag_titre.strip(),
                            'type_ag':    ag_type,
                            'lieu':       ag_lieu.strip() if ag_lieu else None,
                            'president':  ag_president.strip() if ag_president else None,
                            'description': ag_desc.strip() if ag_desc else None,
                        }).execute()
                        st.success(f"✅ AG **{ag_titre}** créée.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

    # ── ONGLET GÉRER ────────────────────────────────────────────
    with ag_tab4:
        st.subheader("🗑️ Supprimer une Assemblée Générale")
        ag_df2 = get_ag_list()
        if ag_df2.empty:
            st.info("Aucune AG à supprimer.")
        else:
            ag_del_opts = ag_df2.apply(lambda r: f"{r['date']} — {r['titre']}", axis=1).tolist()
            sel_del_ag = st.selectbox("AG à supprimer", ag_del_opts, key="ag_del_sel")
            sel_del_ag_id = int(ag_df2.iloc[ag_del_opts.index(sel_del_ag)]['id'])
            items_count = get_ag_items(sel_del_ag_id)
            st.warning(f"⚠️ Supprimer cette AG et ses **{len(items_count)} point(s)** à l'ordre du jour ? "
                       f"Cette action est irréversible.")
            col1, col2 = st.columns(2)
            with col1:
                confirm_ag_del = st.checkbox("Je confirme la suppression", key="chk_ag_del")
            with col2:
                if st.button("🗑️ Supprimer l'AG", key="btn_del_ag",
                             disabled=not confirm_ag_del, use_container_width=True):
                    try:
                        supabase.table('ag_items').delete().eq('ag_id', sel_del_ag_id).execute()
                        supabase.table('ag').delete().eq('id', sel_del_ag_id).execute()
                        st.success("✅ AG supprimée.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

# ==================== GRAND LIVRE GÉNÉRAL ====================
elif menu == "📒 Grand Livre":
    st.markdown("<h1 class='main-header'>📒 Grand Livre Général</h1>", unsafe_allow_html=True)
    st.caption("Toutes les écritures comptables regroupées par compte")

    dep_gl   = get_depenses()
    bud_gl   = get_budget()
    plan_gl  = get_plan_comptable()

    if dep_gl.empty:
        st.info("Aucune dépense enregistrée.")
    else:
        # ---- Normalisation des colonnes ----
        dep_gl['date']        = pd.to_datetime(dep_gl['date'], errors='coerce')
        dep_gl['compte']      = dep_gl['compte'].astype(str).str.strip()
        dep_gl['montant_du']  = pd.to_numeric(dep_gl['montant_du'],  errors='coerce').fillna(0)
        if 'montant_paye' not in dep_gl.columns:
            dep_gl['montant_paye'] = 0.0
        dep_gl['montant_paye'] = pd.to_numeric(dep_gl['montant_paye'], errors='coerce').fillna(0)

        # ---- Jointure plan comptable pour libellé ----
        if not plan_gl.empty:
            plan_gl['compte'] = plan_gl['compte'].astype(str).str.strip()
            libelle_map = plan_gl.set_index('compte')['libelle_compte'].to_dict()
            classe_map  = plan_gl.set_index('compte')['classe'].to_dict()
            famille_map = plan_gl.set_index('compte')['famille'].to_dict()
        else:
            libelle_map = {}; classe_map = {}; famille_map = {}

        # ---- Jointure budget ----
        if not bud_gl.empty:
            bud_gl['compte'] = bud_gl['compte'].astype(str).str.strip()
            bud_map = bud_gl.set_index('compte')['montant_budget'].to_dict()
        else:
            bud_map = {}

        dep_gl['libelle_compte'] = dep_gl['compte'].map(libelle_map).fillna('')
        dep_gl['classe']         = dep_gl['compte'].map(classe_map).fillna('')
        dep_gl['famille']        = dep_gl['compte'].map(famille_map).fillna('')

        # ---- Filtres ----
        col_f1, col_f2, col_f3, col_f4 = st.columns([2,2,2,2])
        with col_f1:
            annees_gl = sorted(dep_gl['date'].dt.year.dropna().astype(int).unique(), reverse=True)
            annee_gl  = st.selectbox("📅 Année", ["Toutes"] + annees_gl, key="gl_annee")
        with col_f2:
            classes_gl = sorted(dep_gl['classe'].dropna().unique())
            classe_gl  = st.selectbox("📂 Classe", ["Toutes"] + classes_gl, key="gl_classe")
        with col_f3:
            comptes_gl = sorted(dep_gl['compte'].unique())
            compte_gl  = st.selectbox("🔢 Compte", ["Tous"] + comptes_gl, key="gl_compte")
        with col_f4:
            affichage_gl = st.radio("📋 Affichage", ["Par compte", "Liste complète"], key="gl_aff",
                                    horizontal=True)

        # Application filtres
        df_gl = dep_gl.copy()
        if annee_gl != "Toutes":
            df_gl = df_gl[df_gl['date'].dt.year == int(annee_gl)]
        if classe_gl != "Toutes":
            df_gl = df_gl[df_gl['classe'] == classe_gl]
        if compte_gl != "Tous":
            df_gl = df_gl[df_gl['compte'] == compte_gl]

        # ---- Métriques globales ----
        total_debit  = df_gl['montant_du'].sum()
        total_paye   = df_gl['montant_paye'].sum()
        total_reste  = total_debit - total_paye
        nb_ecritures = len(df_gl)

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("📝 Écritures",       f"{nb_ecritures}")
        mc2.metric("💸 Total Débit",     f"{total_debit:,.2f} €")
        mc3.metric("✅ Total Réglé",     f"{total_paye:,.2f} €")
        mc4.metric("⏳ Reste à Régler",  f"{total_reste:,.2f} €",
                   delta=f"{-total_reste:,.2f} €" if total_reste > 0 else None,
                   delta_color="inverse")
        st.divider()

        # ---- Export global CSV ----
        export_cols = ['date','compte','libelle_compte','classe','famille',
                       'fournisseur','libelle','montant_du','montant_paye']
        export_cols = [c for c in export_cols if c in df_gl.columns]
        df_export = df_gl[export_cols].copy()
        df_export['date'] = df_export['date'].dt.strftime('%d/%m/%Y')
        df_export.columns = [c.replace('_',' ').title() for c in df_export.columns]
        csv_gl = df_export.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button("📥 Exporter tout le Grand Livre (CSV)", data=csv_gl,
                           file_name=f"grand_livre_{annee_gl}.csv", mime="text/csv",
                           key="dl_gl_global")

        # ==================== AFFICHAGE PAR COMPTE ====================
        if affichage_gl == "Par compte":
            comptes_actifs = sorted(df_gl['compte'].unique())
            if not comptes_actifs:
                st.info("Aucune écriture pour ces filtres.")
            else:
                for cpt in comptes_actifs:
                    df_cpt = df_gl[df_gl['compte'] == cpt].copy()
                    df_cpt = df_cpt.sort_values('date')

                    lib_cpt = libelle_map.get(cpt, df_cpt['libelle_compte'].iloc[0] if not df_cpt.empty else '')
                    budget_cpt = bud_map.get(cpt, 0) or 0
                    total_d    = df_cpt['montant_du'].sum()
                    total_p    = df_cpt['montant_paye'].sum()
                    solde_cpt  = total_d - total_p
                    ecart_bud  = total_d - float(budget_cpt)

                    # Couleur entête selon dépassement
                    if float(budget_cpt) > 0:
                        if ecart_bud > 0:
                            badge = f"🔴 Dépassement {ecart_bud:+,.2f} €"
                            hdr_color = "#4a1a1a"
                        elif ecart_bud < -0.01:
                            badge = f"🟢 Économie {abs(ecart_bud):,.2f} €"
                            hdr_color = "#1a3a2a"
                        else:
                            badge = "✅ Budget exact"
                            hdr_color = "#1a2a3a"
                    else:
                        badge = "⚪ Pas de budget"
                        hdr_color = "#2a2a2a"

                    with st.expander(
                        f"**{cpt}** — {lib_cpt}  |  {len(df_cpt)} écritures  |  "
                        f"Débit: {total_d:,.2f} €  |  Réglé: {total_p:,.2f} €  |  {badge}",
                        expanded=(len(comptes_actifs) == 1)
                    ):
                        # Entête coloré
                        st.markdown(
                            f"<div style='background:{hdr_color};padding:10px 14px;border-radius:6px;"
                            f"margin-bottom:8px;'>"
                            f"<span style='font-size:1.1em;font-weight:bold;color:#eee;'>"
                            f"Compte {cpt} — {lib_cpt}</span><br>"
                            f"<span style='color:#aaa;font-size:0.9em;'>"
                            f"Budget: {float(budget_cpt):,.2f} €  |  "
                            f"Classe {df_cpt['classe'].iloc[0]}  |  {badge}</span></div>",
                            unsafe_allow_html=True
                        )

                        # Tableau des écritures avec solde cumulé
                        rows = []
                        solde_cum = 0.0
                        for _, r in df_cpt.iterrows():
                            solde_cum += float(r['montant_du'])
                            rows.append({
                                'Date':        r['date'].strftime('%d/%m/%Y') if pd.notna(r['date']) else '—',
                                'Fournisseur': str(r.get('fournisseur','') or ''),
                                'Libellé':     str(r.get('libelle','') or ''),
                                'Débit (€)':   float(r['montant_du']),
                                'Réglé (€)':   float(r['montant_paye']),
                                'Reste (€)':   float(r['montant_du']) - float(r['montant_paye']),
                                'Solde cumulé (€)': round(solde_cum, 2),
                            })

                        # Ligne de total
                        rows.append({
                            'Date':        '**TOTAL**',
                            'Fournisseur': '',
                            'Libellé':     f'{len(df_cpt)} écritures',
                            'Débit (€)':   total_d,
                            'Réglé (€)':   total_p,
                            'Reste (€)':   solde_cpt,
                            'Solde cumulé (€)': total_d,
                        })

                        df_show = pd.DataFrame(rows)
                        st.dataframe(
                            df_show,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'Débit (€)':        st.column_config.NumberColumn("Débit (€)",   format="%.2f"),
                                'Réglé (€)':        st.column_config.NumberColumn("Réglé (€)",   format="%.2f"),
                                'Reste (€)':        st.column_config.NumberColumn("Reste (€)",   format="%.2f"),
                                'Solde cumulé (€)': st.column_config.NumberColumn("Solde cum. (€)", format="%.2f"),
                            }
                        )

                        # Mini-ligne budget vs réel
                        if float(budget_cpt) > 0:
                            pct_consomme = min(total_d / float(budget_cpt) * 100, 100)
                            c1b, c2b, c3b = st.columns(3)
                            c1b.metric("Budget", f"{float(budget_cpt):,.2f} €")
                            c2b.metric("Dépensé", f"{total_d:,.2f} €", delta=f"{ecart_bud:+,.2f} €",
                                       delta_color="inverse")
                            c3b.metric("Consommé", f"{pct_consomme:.1f}%")
                            st.progress(int(pct_consomme))

                # ---- Tableau de synthèse final ----
                st.divider()
                st.subheader("📊 Synthèse par compte")
                synth_rows = []
                for cpt in comptes_actifs:
                    df_c = df_gl[df_gl['compte'] == cpt]
                    bud  = float(bud_map.get(cpt, 0) or 0)
                    dep  = float(df_c['montant_du'].sum())
                    pay  = float(df_c['montant_paye'].sum())
                    synth_rows.append({
                        'Compte':     cpt,
                        'Libellé':    libelle_map.get(cpt, ''),
                        'Classe':     str(classe_map.get(cpt, '')),
                        'Budget (€)': bud,
                        'Débit (€)':  dep,
                        'Réglé (€)':  pay,
                        'Reste (€)':  dep - pay,
                        'Écart/Budget (€)': dep - bud,
                        '% Consommé': round(dep/bud*100, 1) if bud > 0 else None,
                    })

                # Ligne TOTAL
                synth_rows.append({
                    'Compte':     'TOTAL',
                    'Libellé':    '',
                    'Classe':     '',
                    'Budget (€)': sum(r['Budget (€)'] for r in synth_rows),
                    'Débit (€)':  sum(r['Débit (€)']  for r in synth_rows),
                    'Réglé (€)':  sum(r['Réglé (€)']  for r in synth_rows),
                    'Reste (€)':  sum(r['Reste (€)']  for r in synth_rows),
                    'Écart/Budget (€)': sum(r['Écart/Budget (€)'] for r in synth_rows),
                    '% Consommé': None,
                })

                df_synth = pd.DataFrame(synth_rows)
                st.dataframe(
                    df_synth,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'Budget (€)':        st.column_config.NumberColumn("Budget (€)",     format="%.2f"),
                        'Débit (€)':         st.column_config.NumberColumn("Débit (€)",      format="%.2f"),
                        'Réglé (€)':         st.column_config.NumberColumn("Réglé (€)",      format="%.2f"),
                        'Reste (€)':         st.column_config.NumberColumn("Reste (€)",      format="%.2f"),
                        'Écart/Budget (€)':  st.column_config.NumberColumn("Écart Bud. (€)", format="%+.2f"),
                        '% Consommé':        st.column_config.NumberColumn("% Conso.",        format="%.1f%%"),
                    }
                )

        # ==================== LISTE COMPLÈTE ====================
        else:
            if df_gl.empty:
                st.info("Aucune écriture pour ces filtres.")
            else:
                df_list = df_gl.copy().sort_values(['compte','date'])
                df_list['date_fmt'] = df_list['date'].dt.strftime('%d/%m/%Y')
                cols_show = {
                    'date_fmt':       'Date',
                    'compte':         'Compte',
                    'libelle_compte': 'Libellé compte',
                    'classe':         'Classe',
                    'fournisseur':    'Fournisseur',
                    'libelle':        'Libellé',
                    'montant_du':     'Débit (€)',
                    'montant_paye':   'Réglé (€)',
                }
                cols_disp = [c for c in cols_show if c in df_list.columns]
                df_list_show = df_list[cols_disp].copy()
                df_list_show.columns = [cols_show[c] for c in cols_disp]
                # Calcul Reste
                if 'Débit (€)' in df_list_show.columns and 'Réglé (€)' in df_list_show.columns:
                    df_list_show['Reste (€)'] = df_list_show['Débit (€)'] - df_list_show['Réglé (€)']

                st.dataframe(
                    df_list_show,
                    use_container_width=True,
                    hide_index=True,
                    height=600,
                    column_config={
                        'Débit (€)':  st.column_config.NumberColumn("Débit (€)",  format="%.2f"),
                        'Réglé (€)':  st.column_config.NumberColumn("Réglé (€)",  format="%.2f"),
                        'Reste (€)':  st.column_config.NumberColumn("Reste (€)",  format="%.2f"),
                    }
                )


# ==================== CONTRATS FOURNISSEURS ====================
elif menu == "📑 Contrats Fournisseurs":
    st.markdown("<h1 class='main-header'>📑 Contrats Fournisseurs</h1>", unsafe_allow_html=True)
    st.caption("Gérez les contrats liant la copropriété à ses prestataires")

    @st.cache_data(ttl=60)
    def get_contrats():
        try:
            r = supabase.table('contrats').select('*').order('date_debut', desc=True).execute()
            return pd.DataFrame(r.data) if r.data else pd.DataFrame()
        except Exception as e:
            st.error(f"❌ {e}"); return pd.DataFrame()

    def upload_contrat_doc(contrat_id, file_bytes, filename):
        ext = filename.rsplit('.', 1)[-1].lower()
        path = f"contrats/{contrat_id}/{filename}"
        content_type = 'application/pdf' if ext == 'pdf' else f'image/{ext}'
        try:
            supabase.storage.from_('factures').remove([path])
        except:
            pass
        supabase.storage.from_('factures').upload(path, file_bytes,
            file_options={"content-type": content_type, "upsert": "true"})
        supabase.table('contrats').update({'document_path': path}).eq('id', contrat_id).execute()
        return path

    TYPES_CONTRAT = [
        "Entretien ascenseur", "Nettoyage parties communes", "Gardiennage / Conciergerie",
        "Assurance immeuble", "Maintenance chauffage", "Espaces verts",
        "Électricité parties communes", "Eau", "Gaz", "Désinfection / Nuisibles",
        "Syndic", "Autre"
    ]
    STATUTS = ["En cours", "À renouveler", "Résilié", "En négociation"]

    ct1, ct2, ct3, ct4 = st.tabs(["📋 Tous les contrats", "➕ Nouveau contrat", "✏️ Modifier", "🗑️ Supprimer"])

    # ── TAB 1 : Liste ──────────────────────────────────────────────
    with ct1:
        df_ct = get_contrats()

        if df_ct.empty:
            st.info("Aucun contrat enregistré. Ajoutez-en un dans l'onglet ➕ Nouveau contrat.")
        else:
            # Normalisation
            for col_d in ['date_debut','date_fin','date_echeance']:
                if col_d in df_ct.columns:
                    df_ct[col_d] = pd.to_datetime(df_ct[col_d], errors='coerce')
            if 'montant_annuel' in df_ct.columns:
                df_ct['montant_annuel'] = pd.to_numeric(df_ct['montant_annuel'], errors='coerce').fillna(0)

            # Métriques
            nb_total   = len(df_ct)
            nb_cours   = len(df_ct[df_ct.get('statut','') == 'En cours']) if 'statut' in df_ct.columns else 0
            nb_renouv  = len(df_ct[df_ct.get('statut','') == 'À renouveler']) if 'statut' in df_ct.columns else 0
            total_an   = float(df_ct['montant_annuel'].sum()) if 'montant_annuel' in df_ct.columns else 0

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("📑 Contrats total", nb_total)
            mc2.metric("✅ En cours", nb_cours)
            mc3.metric("⚠️ À renouveler", nb_renouv)
            mc4.metric("💰 Coût annuel total", f"{total_an:,.0f} €")

            # Alertes échéance dans 60 jours
            today = pd.Timestamp.today().normalize()
            if 'date_echeance' in df_ct.columns:
                proches = df_ct[
                    df_ct['date_echeance'].notna() &
                    (df_ct['date_echeance'] >= today) &
                    (df_ct['date_echeance'] <= today + pd.Timedelta(days=60))
                ]
                for _, r in proches.iterrows():
                    jours = (r['date_echeance'] - today).days
                    st.warning(f"⏰ **{r.get('fournisseur','')}** — {r.get('type_contrat','')} : "
                               f"échéance dans **{jours} jour(s)** ({r['date_echeance'].strftime('%d/%m/%Y')})")

            st.divider()

            # Filtres
            fcol1, fcol2, fcol3 = st.columns(3)
            with fcol1:
                types_dispo = ["Tous"] + sorted(df_ct['type_contrat'].dropna().unique().tolist()) if 'type_contrat' in df_ct.columns else ["Tous"]
                filt_type = st.selectbox("📂 Type", types_dispo, key="ct_filt_type")
            with fcol2:
                statuts_dispo = ["Tous"] + STATUTS
                filt_statut = st.selectbox("🔵 Statut", statuts_dispo, key="ct_filt_statut")
            with fcol3:
                filt_search = st.text_input("🔍 Rechercher fournisseur", key="ct_search")

            df_show = df_ct.copy()
            if filt_type   != "Tous" and 'type_contrat' in df_show.columns:
                df_show = df_show[df_show['type_contrat'] == filt_type]
            if filt_statut != "Tous" and 'statut' in df_show.columns:
                df_show = df_show[df_show['statut'] == filt_statut]
            if filt_search and 'fournisseur' in df_show.columns:
                df_show = df_show[df_show['fournisseur'].str.contains(filt_search, case=False, na=False)]

            # Tableau principal
            cols_tab = ['fournisseur','type_contrat','statut','montant_annuel',
                        'date_debut','date_fin','date_echeance','tacite_reconduction']
            cols_tab = [c for c in cols_tab if c in df_show.columns]
            df_tab   = df_show[cols_tab].copy()
            for col_d in ['date_debut','date_fin','date_echeance']:
                if col_d in df_tab.columns:
                    df_tab[col_d] = df_tab[col_d].apply(
                        lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else '—')

            st.dataframe(
                df_tab,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'fournisseur':        st.column_config.TextColumn("Fournisseur"),
                    'type_contrat':       st.column_config.TextColumn("Type"),
                    'statut':             st.column_config.TextColumn("Statut"),
                    'montant_annuel':     st.column_config.NumberColumn("Montant annuel (€)", format="%.2f"),
                    'date_debut':         st.column_config.TextColumn("Début"),
                    'date_fin':           st.column_config.TextColumn("Fin"),
                    'date_echeance':      st.column_config.TextColumn("Échéance préavis"),
                    'tacite_reconduction':st.column_config.CheckboxColumn("Tacite recon."),
                }
            )

            # Détail + document d'un contrat sélectionné
            st.divider()
            st.subheader("📄 Détail & Document")
            labels_ct = df_show.apply(
                lambda r: f"{r.get('fournisseur','')} — {r.get('type_contrat','')} "
                          f"({'✅' if r.get('document_path') else '📄'})", axis=1).tolist()
            if labels_ct:
                sel_ct_label = st.selectbox("Sélectionner un contrat", labels_ct, key="ct_sel_detail")
                sel_ct_row   = df_show.iloc[labels_ct.index(sel_ct_label)]
                sel_ct_id    = int(sel_ct_row['id'])
                doc_path     = sel_ct_row.get('document_path', None)
                has_doc      = bool(doc_path and str(doc_path) not in ('','None','nan'))

                col_info, col_doc = st.columns(2)
                with col_info:
                    st.markdown("**Informations contrat**")
                    infos = {
                        "Fournisseur":    sel_ct_row.get('fournisseur',''),
                        "Type":           sel_ct_row.get('type_contrat',''),
                        "Statut":         sel_ct_row.get('statut',''),
                        "Montant annuel": f"{float(sel_ct_row.get('montant_annuel',0) or 0):,.2f} €",
                        "Début":          pd.to_datetime(sel_ct_row.get('date_debut')).strftime('%d/%m/%Y') if pd.notna(sel_ct_row.get('date_debut')) else '—',
                        "Fin":            pd.to_datetime(sel_ct_row.get('date_fin')).strftime('%d/%m/%Y') if pd.notna(sel_ct_row.get('date_fin')) else '—',
                        "Échéance":       pd.to_datetime(sel_ct_row.get('date_echeance')).strftime('%d/%m/%Y') if pd.notna(sel_ct_row.get('date_echeance')) else '—',
                        "Tacite recon.":  "Oui" if sel_ct_row.get('tacite_reconduction') else "Non",
                        "Préavis":        f"{sel_ct_row.get('preavis_mois', '—')} mois",
                        "Notes":          sel_ct_row.get('notes','') or '—',
                    }
                    for k, v in infos.items():
                        st.markdown(f"**{k}** : {v}")

                    st.divider()
                    st.markdown("**📎 Joindre le contrat (PDF)**")
                    up_doc = st.file_uploader("PDF ou image", type=["pdf","jpg","jpeg","png"],
                                              key=f"up_ct_{sel_ct_id}")
                    if up_doc:
                        if st.button("📤 Envoyer le document", key=f"btn_up_ct_{sel_ct_id}",
                                     type="primary", use_container_width=True):
                            try:
                                upload_contrat_doc(sel_ct_id, up_doc.read(), up_doc.name)
                                st.success("✅ Document uploadé.")
                                st.cache_data.clear(); st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")
                    if has_doc:
                        if st.button("🗑️ Supprimer le document", key=f"del_doc_ct_{sel_ct_id}",
                                     use_container_width=True):
                            try:
                                supabase.storage.from_('factures').remove([str(doc_path)])
                                supabase.table('contrats').update({'document_path': None}).eq('id', sel_ct_id).execute()
                                st.success("✅ Document supprimé.")
                                st.cache_data.clear(); st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

                with col_doc:
                    if has_doc:
                        st.markdown("**📄 Document**")
                        try:
                            afficher_facture(str(doc_path), height=600)
                        except Exception as e:
                            st.error(f"❌ {e}")
                    else:
                        st.markdown(
                            "<div style='border:2px dashed #444;border-radius:8px;height:420px;"
                            "display:flex;align-items:center;justify-content:center;"
                            "flex-direction:column;gap:12px;'>"
                            "<span style='font-size:3em;'>📑</span>"
                            "<span style='color:#666;'>Aucun document joint</span></div>",
                            unsafe_allow_html=True)

            # Export CSV
            csv_ct = df_tab.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button("📥 Exporter CSV", data=csv_ct,
                               file_name="contrats_fournisseurs.csv", mime="text/csv", key="dl_ct")

    # ── TAB 2 : Nouveau contrat ────────────────────────────────────
    with ct2:
        st.subheader("➕ Ajouter un contrat")
        with st.form("form_new_contrat", clear_on_submit=True):
            nf1, nf2 = st.columns(2)
            with nf1:
                nf_fourn   = st.text_input("Fournisseur *", placeholder="Ex: OTIS, Ménagère du 8ème…")
                nf_type    = st.selectbox("Type de contrat *", TYPES_CONTRAT)
                nf_statut  = st.selectbox("Statut", STATUTS)
                nf_montant = st.number_input("Montant annuel HT (€)", min_value=0.0, step=10.0)
            with nf2:
                nf_debut   = st.date_input("Date de début", key="nf_debut")
                nf_fin     = st.date_input("Date de fin (si définie)", value=None, key="nf_fin")
                nf_echeance= st.date_input("Date d'échéance préavis", value=None, key="nf_ech")
                nf_preavis = st.number_input("Préavis (mois)", min_value=0, max_value=24, value=3, step=1)
            nf_tacite  = st.checkbox("Tacite reconduction")
            nf_notes   = st.text_area("Notes / Observations", height=80)
            submitted  = st.form_submit_button("💾 Créer le contrat", type="primary",
                                               use_container_width=True)

        if submitted:
            if not nf_fourn.strip():
                st.error("❌ Le nom du fournisseur est obligatoire.")
            else:
                try:
                    payload = {
                        'fournisseur':         nf_fourn.strip(),
                        'type_contrat':        nf_type,
                        'statut':              nf_statut,
                        'montant_annuel':      float(nf_montant),
                        'date_debut':          nf_debut.strftime('%Y-%m-%d'),
                        'date_fin':            nf_fin.strftime('%Y-%m-%d') if nf_fin else None,
                        'date_echeance':       nf_echeance.strftime('%Y-%m-%d') if nf_echeance else None,
                        'preavis_mois':        int(nf_preavis),
                        'tacite_reconduction': nf_tacite,
                        'notes':               nf_notes.strip() or None,
                    }
                    supabase.table('contrats').insert(payload).execute()
                    st.success(f"✅ Contrat **{nf_fourn}** créé.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ {e}")

    # ── TAB 3 : Modifier ──────────────────────────────────────────
    with ct3:
        st.subheader("✏️ Modifier un contrat")
        df_mod = get_contrats()
        if df_mod.empty:
            st.info("Aucun contrat.")
        else:
            labels_mod = df_mod.apply(
                lambda r: f"{r.get('fournisseur','')} — {r.get('type_contrat','')}", axis=1).tolist()
            sel_mod = st.selectbox("Sélectionner", labels_mod, key="ct_mod_sel")
            row_mod = df_mod.iloc[labels_mod.index(sel_mod)]
            mod_id  = int(row_mod['id'])

            with st.form(f"form_mod_{mod_id}"):
                mf1, mf2 = st.columns(2)
                with mf1:
                    m_fourn  = st.text_input("Fournisseur", value=str(row_mod.get('fournisseur','') or ''))
                    m_type   = st.selectbox("Type", TYPES_CONTRAT,
                                            index=TYPES_CONTRAT.index(row_mod['type_contrat'])
                                            if row_mod.get('type_contrat') in TYPES_CONTRAT else 0)
                    m_statut = st.selectbox("Statut", STATUTS,
                                            index=STATUTS.index(row_mod['statut'])
                                            if row_mod.get('statut') in STATUTS else 0)
                    m_montant= st.number_input("Montant annuel HT (€)",
                                               value=float(row_mod.get('montant_annuel',0) or 0),
                                               min_value=0.0, step=10.0)
                with mf2:
                    m_debut  = st.date_input("Date début",
                                             value=pd.to_datetime(row_mod['date_debut']).date()
                                             if pd.notna(row_mod.get('date_debut')) else None,
                                             key="m_debut")
                    m_fin    = st.date_input("Date fin",
                                             value=pd.to_datetime(row_mod['date_fin']).date()
                                             if pd.notna(row_mod.get('date_fin')) else None,
                                             key="m_fin")
                    m_ech    = st.date_input("Échéance préavis",
                                             value=pd.to_datetime(row_mod['date_echeance']).date()
                                             if pd.notna(row_mod.get('date_echeance')) else None,
                                             key="m_ech")
                    m_preavis= st.number_input("Préavis (mois)",
                                               value=int(row_mod.get('preavis_mois',3) or 3),
                                               min_value=0, max_value=24, step=1)
                m_tacite = st.checkbox("Tacite reconduction", value=bool(row_mod.get('tacite_reconduction', False)))
                m_notes  = st.text_area("Notes", value=str(row_mod.get('notes','') or ''), height=80)
                save_mod = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)

            if save_mod:
                try:
                    supabase.table('contrats').update({
                        'fournisseur':         m_fourn.strip(),
                        'type_contrat':        m_type,
                        'statut':              m_statut,
                        'montant_annuel':      float(m_montant),
                        'date_debut':          m_debut.strftime('%Y-%m-%d') if m_debut else None,
                        'date_fin':            m_fin.strftime('%Y-%m-%d') if m_fin else None,
                        'date_echeance':       m_ech.strftime('%Y-%m-%d') if m_ech else None,
                        'preavis_mois':        int(m_preavis),
                        'tacite_reconduction': m_tacite,
                        'notes':               m_notes.strip() or None,
                    }).eq('id', mod_id).execute()
                    st.success("✅ Contrat mis à jour.")
                    st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

    # ── TAB 4 : Supprimer ─────────────────────────────────────────
    with ct4:
        st.subheader("🗑️ Supprimer un contrat")
        df_del = get_contrats()
        if df_del.empty:
            st.info("Aucun contrat.")
        else:
            labels_del = df_del.apply(
                lambda r: f"{r.get('fournisseur','')} — {r.get('type_contrat','')}", axis=1).tolist()
            sel_del  = st.selectbox("Sélectionner", labels_del, key="ct_del_sel")
            row_del  = df_del.iloc[labels_del.index(sel_del)]
            del_id   = int(row_del['id'])
            doc_del  = row_del.get('document_path', None)

            st.warning(f"⚠️ Supprimer le contrat **{row_del.get('fournisseur','')}** "
                       f"— {row_del.get('type_contrat','')} ? Cette action est irréversible.")
            if doc_del and str(doc_del) not in ('','None','nan'):
                st.info(f"📎 Le document associé ({doc_del}) sera également supprimé du stockage.")
            confirm_del = st.checkbox("Je confirme la suppression", key="ct_del_confirm")
            if st.button("🗑️ Supprimer", disabled=not confirm_del, key="ct_del_btn",
                         use_container_width=True):
                try:
                    if doc_del and str(doc_del) not in ('','None','nan'):
                        supabase.storage.from_('factures').remove([str(doc_del)])
                    supabase.table('contrats').delete().eq('id', del_id).execute()
                    st.success("✅ Contrat supprimé.")
                    st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")


# ==================== COMMUNICATIONS ====================
elif menu == "📬 Communications":
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import urllib.parse

    st.markdown("<h1 class='main-header'>📬 Communications</h1>", unsafe_allow_html=True)
    st.caption("Envoyez des emails, SMS ou messages WhatsApp aux copropriétaires")

    # ── Chargement copropriétaires ──────────────────────────────
    copro_comm = get_coproprietaires()
    if copro_comm.empty:
        st.error("❌ Impossible de charger les copropriétaires."); st.stop()
    copro_comm = prepare_copro(copro_comm)
    for col_c in ['email','telephone','whatsapp']:
        if col_c not in copro_comm.columns:
            copro_comm[col_c] = None if col_c != 'whatsapp' else False
    copro_comm['whatsapp'] = copro_comm['whatsapp'].fillna(False).astype(bool)

    # ── Configuration SMTP (depuis st.secrets ou saisie manuelle) ──
    def get_smtp_config():
        try:
            return {
                'host':     st.secrets.get("smtp_host", "smtp.gmail.com"),
                'port':     int(st.secrets.get("smtp_port", 587)),
                'user':     st.secrets.get("smtp_user", ""),
                'password': st.secrets.get("smtp_password", ""),
                'from':     st.secrets.get("smtp_from", ""),
            }
        except:
            return {'host':'smtp.gmail.com','port':587,'user':'','password':'','from':''}

    # ─────────────────────────────────────────────────────────────
    # SÉLECTION DES DESTINATAIRES
    # ─────────────────────────────────────────────────────────────
    st.subheader("👥 Sélection des destinataires")

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        mode_sel = st.radio("Mode de sélection", 
            ["✅ Tous", "🔍 Sélection manuelle", "📧 Avec email", "💬 WhatsApp uniquement"],
            horizontal=True, key="comm_mode_sel")

    with col_sel2:
        canal = st.radio("Canal", ["📧 Email", "💬 WhatsApp", "📱 SMS"], 
                         horizontal=True, key="comm_canal")

    # Appliquer filtre selon canal pour les destinataires disponibles
    if canal == "📧 Email":
        dispo = copro_comm[copro_comm['email'].apply(
            lambda x: bool(x) and str(x) not in ('','None','nan'))]
    elif canal == "💬 WhatsApp":
        dispo = copro_comm[copro_comm['whatsapp'] == True]
    else:  # SMS
        dispo = copro_comm[copro_comm['telephone'].apply(
            lambda x: bool(x) and str(x) not in ('','None','nan'))]

    # Sélection
    if mode_sel == "✅ Tous":
        destinataires = dispo
    elif mode_sel == "📧 Avec email":
        destinataires = copro_comm[copro_comm['email'].apply(
            lambda x: bool(x) and str(x) not in ('','None','nan'))]
        if canal != "📧 Email":
            destinataires = destinataires[destinataires.index.isin(dispo.index)]
    elif mode_sel == "💬 WhatsApp uniquement":
        destinataires = copro_comm[copro_comm['whatsapp'] == True]
        if canal != "💬 WhatsApp":
            destinataires = destinataires[destinataires.index.isin(dispo.index)]
    else:  # Sélection manuelle
        noms_dispo = dispo['nom'].tolist()
        sel_noms = st.multiselect("Choisir les copropriétaires", noms_dispo, 
                                   default=[], key="comm_sel_noms")
        destinataires = copro_comm[copro_comm['nom'].isin(sel_noms)]

    # Résumé destinataires
    nb_dest = len(destinataires)
    if nb_dest == 0:
        st.warning(f"⚠️ Aucun destinataire disponible pour le canal **{canal}**. "
                   f"Vérifiez que les coordonnées sont renseignées dans **👥 Copropriétaires**.")
    else:
        with st.expander(f"✅ {nb_dest} destinataire(s) sélectionné(s)", expanded=False):
            for _, r in destinataires.iterrows():
                contact = r.get('email','') if canal=="📧 Email" else r.get('telephone','')
                wa_badge = " 💬" if r.get('whatsapp') else ""
                st.markdown(f"- **Lot {int(r.get('lot',0))}** — {r['nom']} | {contact}{wa_badge}")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # RÉDACTION DU MESSAGE
    # ─────────────────────────────────────────────────────────────
    st.subheader("✍️ Message")

    # Templates prédéfinis
    templates = {
        "— Choisir un modèle —": ("", ""),
        "📋 Convocation AG": (
            "Convocation Assemblée Générale — {residence}",
            "Madame, Monsieur,\n\nNous avons le plaisir de vous convoquer à l'Assemblée Générale "
            "de la copropriété qui se tiendra le [DATE] à [HEURE] au [LIEU].\n\n"
            "L'ordre du jour sera le suivant :\n- [POINT 1]\n- [POINT 2]\n\n"
            "Nous vous prions de bien vouloir agréer nos salutations distinguées.\n\nLe Syndic"
        ),
        "💰 Appel de charges": (
            "Appel de charges — {residence}",
            "Madame, Monsieur,\n\nNous vous informons qu'un appel de charges d'un montant de "
            "[MONTANT] € est dû pour le [TRIMESTRE] [ANNÉE].\n\n"
            "Merci de bien vouloir effectuer votre règlement avant le [DATE LIMITE].\n\n"
            "RIB disponible sur demande.\n\nCordialement,\nLe Syndic"
        ),
        "🔧 Travaux — information": (
            "Information travaux — {residence}",
            "Madame, Monsieur,\n\nNous vous informons que des travaux de [NATURE DES TRAVAUX] "
            "seront effectués du [DATE DÉBUT] au [DATE FIN].\n\n"
            "Des perturbations sont possibles. Nous vous prions de nous excuser pour la gêne occasionnée.\n\n"
            "Cordialement,\nLe Syndic"
        ),
        "⚠️ Impayé — relance": (
            "Relance — Solde impayé — {residence}",
            "Madame, Monsieur,\n\nSauf erreur de notre part, nous constatons un solde impayé "
            "de [MONTANT] € sur votre compte copropriétaire.\n\n"
            "Nous vous remercions de régulariser cette situation dans les meilleurs délais.\n\n"
            "Cordialement,\nLe Syndic"
        ),
        "📝 Message libre": ("", ""),
    }

    tpl_choix = st.selectbox("📝 Modèle de message", list(templates.keys()), key="comm_tpl")
    tpl_sujet, tpl_corps = templates[tpl_choix]
    residence = "la copropriété"  # peut être personnalisé

    col_msg1, col_msg2 = st.columns([2, 1])
    with col_msg1:
        if canal == "📧 Email":
            sujet = st.text_input("Objet *", 
                value=tpl_sujet.replace("{residence}", residence),
                key="comm_sujet")
        corps = st.text_area("Message *", 
            value=tpl_corps.replace("\\n", "\n").replace("{residence}", residence),
            height=250, key="comm_corps",
            help="💡 Vous pouvez utiliser {nom} pour personnaliser avec le nom du destinataire")
        personnaliser = st.checkbox("🎯 Personnaliser avec le nom ({nom})", value=True,
                                    key="comm_perso",
                                    help="Remplace {nom} par le nom de chaque destinataire")
    with col_msg2:
        st.markdown("**Aperçu**")
        apercu_nom = destinataires.iloc[0]['nom'] if nb_dest > 0 else "Dupont"
        corps_apercu = corps.replace("{nom}", apercu_nom) if personnaliser else corps
        st.markdown(
            f"<div style='background:#1a1a2e;padding:12px;border-radius:6px;"
            f"font-size:0.85em;color:#ddd;white-space:pre-wrap;max-height:300px;overflow-y:auto;'>"
            f"{corps_apercu}</div>",
            unsafe_allow_html=True
        )
        if nb_dest > 1:
            st.caption(f"🔁 Ce message sera envoyé {nb_dest} fois (1 par destinataire)")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # ENVOI
    # ─────────────────────────────────────────────────────────────

    # ══════════════════════════════════
    # 📧 EMAIL
    # ══════════════════════════════════
    if canal == "📧 Email":
        email_method = st.radio(
            "📡 Méthode d'envoi",
            ["🚀 Brevo (recommandé — gratuit)", "⚙️ SMTP (Gmail / OVH / autre)"],
            horizontal=True, key="email_method",
            help="Brevo ne nécessite pas de configuration complexe — juste une clé API gratuite"
        )

        # ── BREVO ──────────────────────────────────────────────────
        if email_method == "🚀 Brevo (recommandé — gratuit)":
            with st.expander("⚙️ Configuration Brevo", expanded=True):
                st.markdown("""
**Brevo est gratuit jusqu'à 300 emails/jour** — aucune carte bancaire requise.

**Étapes d'inscription (2 minutes) :**
1. Allez sur [brevo.com](https://www.brevo.com) → Inscription gratuite
2. Menu → **Paramètres → Clés API** → Générer une clé
3. Copiez la clé et collez-la ci-dessous
""")
                try:
                    brevo_key     = st.secrets.get("brevo_api_key", "")
                    brevo_from_em = st.secrets.get("brevo_from_email", "")
                    brevo_from_nm = st.secrets.get("brevo_from_name", "Syndic Copropriété")
                except:
                    brevo_key = brevo_from_em = brevo_from_nm = ""

                if not brevo_key:
                    brevo_key     = st.text_input("🔑 Clé API Brevo", type="password",
                                                  key="brevo_k", placeholder="xkeysib-...")
                    brevo_from_em = st.text_input("📧 Votre email expéditeur",
                                                  key="brevo_fe", placeholder="syndic@monimmeuble.fr")
                    brevo_from_nm = st.text_input("👤 Nom expéditeur",
                                                  key="brevo_fn", value="Syndic Copropriété")
                else:
                    st.success("✅ Clé API Brevo chargée depuis les secrets.")
                    brevo_from_em = st.text_input("📧 Email expéditeur",
                                                  value=brevo_from_em, key="brevo_fe2")
                    brevo_from_nm = st.text_input("👤 Nom expéditeur",
                                                  value=brevo_from_nm, key="brevo_fn2")
                st.caption("Pour enregistrer définitivement : Streamlit Cloud → Settings → Secrets")
                st.code('brevo_api_key    = "xkeysib-..."\nbrevo_from_email = "votre@email.fr"\nbrevo_from_name  = "Syndic Copropriété"', language="toml")

            if st.button("📧 Envoyer via Brevo", type="primary",
                         disabled=(nb_dest == 0 or not corps.strip()),
                         use_container_width=True, key="btn_brevo"):
                if not brevo_key or not brevo_from_em:
                    st.error("❌ Renseignez la clé API Brevo et votre email expéditeur.")
                else:
                    import urllib.request, json as _json
                    progress = st.progress(0, text="Envoi via Brevo…")
                    ok_list, err_list = [], []
                    for i, (_, cop) in enumerate(destinataires.iterrows()):
                        dest_email = str(cop.get('email','') or '').strip()
                        if not dest_email or dest_email in ('None','nan'):
                            err_list.append(f"{cop['nom']} — pas d'email")
                            continue
                        corps_perso = corps.replace("{nom}", cop['nom']) if personnaliser else corps
                        html_body   = corps_perso.replace("\n","<br>")
                        payload = _json.dumps({
                            "sender":      {"name": brevo_from_nm, "email": brevo_from_em},
                            "to":          [{"email": dest_email, "name": cop['nom']}],
                            "subject":     sujet,
                            "textContent": corps_perso,
                            "htmlContent": f"<html><body style='font-family:Arial,sans-serif'><p>{html_body}</p></body></html>",
                        }).encode('utf-8')
                        try:
                            req = urllib.request.Request(
                                "https://api.brevo.com/v3/smtp/email",
                                data=payload,
                                headers={
                                    "accept":       "application/json",
                                    "content-type": "application/json",
                                    "api-key":      brevo_key,
                                },
                                method="POST"
                            )
                            with urllib.request.urlopen(req) as resp:
                                resp.read()
                            ok_list.append(f"✅ {cop['nom']} ({dest_email})")
                        except urllib.error.HTTPError as e:
                            detail = e.read().decode('utf-8', errors='ignore')
                            try:
                                import json as _j2
                                d = _j2.loads(detail)
                                msg_err = d.get('message', detail)
                            except:
                                msg_err = detail
                            err_list.append(f"❌ {cop['nom']} — HTTP {e.code}: {msg_err}")
                        except Exception as e:
                            err_list.append(f"❌ {cop['nom']} — {e}")
                        progress.progress((i+1)/nb_dest,
                                          text=f"Envoi {i+1}/{nb_dest} — {cop['nom']}")
                    progress.empty()
                    if ok_list:
                        st.success(f"✅ {len(ok_list)} email(s) envoyé(s) via Brevo")
                        with st.expander("Détail"):
                            for l in ok_list: st.markdown(l)
                    if err_list:
                        st.error(f"❌ {len(err_list)} erreur(s)")
                        for l in err_list: st.markdown(l)

        # ── SMTP ───────────────────────────────────────────────────
        else:
            smtp_cfg = get_smtp_config()
            with st.expander("⚙️ Configuration SMTP", expanded=not bool(smtp_cfg['user'])):
                st.markdown("""
**Gmail** : créez un [mot de passe d'application](https://myaccount.google.com/apppasswords)
(Compte Google → Sécurité → Validation 2 étapes activée → Mots de passe des applications)

**OVH / autre** : utilisez les paramètres SMTP de votre hébergeur.
""")
                smtp_host = st.text_input("Serveur SMTP", value=smtp_cfg['host'], key="smtp_h")
                smtp_port = st.number_input("Port", value=smtp_cfg['port'], min_value=25, key="smtp_p")
                smtp_user = st.text_input("Identifiant", value=smtp_cfg['user'], key="smtp_u")
                smtp_pass = st.text_input("Mot de passe / Clé app", value=smtp_cfg['password'],
                                           type="password", key="smtp_pw")
                smtp_from = st.text_input("Expéditeur affiché",
                                           value=smtp_cfg['from'] or smtp_cfg['user'],
                                           key="smtp_f", placeholder="Syndic <mail@gmail.com>")

            if st.button("📧 Envoyer via SMTP", type="primary",
                         disabled=(nb_dest == 0 or not corps.strip()),
                         use_container_width=True, key="btn_send_email"):
                if not smtp_user or not smtp_pass:
                    st.error("❌ Configurez le serveur SMTP avant d'envoyer.")
                else:
                    progress = st.progress(0, text="Envoi en cours…")
                    ok_list, err_list = [], []
                    for i, (_, cop) in enumerate(destinataires.iterrows()):
                        dest_email = str(cop.get('email','') or '').strip()
                        if not dest_email or dest_email in ('None','nan'):
                            err_list.append(f"{cop['nom']} — pas d'email")
                            continue
                        corps_perso = corps.replace("{nom}", cop['nom']) if personnaliser else corps
                        try:
                            msg = MIMEMultipart('alternative')
                            msg['Subject'] = sujet
                            msg['From']    = smtp_from or smtp_user
                            msg['To']      = dest_email
                            msg.attach(MIMEText(corps_perso, 'plain', 'utf-8'))
                            html_body = corps_perso.replace("\n","<br>")
                            msg.attach(MIMEText(
                                f"<html><body><p>{html_body}</p></body></html>",
                                'html', 'utf-8'))
                            with smtplib.SMTP(smtp_host, int(smtp_port)) as srv:
                                srv.ehlo(); srv.starttls(); srv.ehlo()
                                srv.login(smtp_user, smtp_pass)
                                srv.sendmail(smtp_user, dest_email, msg.as_string())
                            ok_list.append(f"✅ {cop['nom']} ({dest_email})")
                        except Exception as e:
                            err_list.append(f"❌ {cop['nom']} — {e}")
                        progress.progress((i+1)/nb_dest,
                                          text=f"Envoi {i+1}/{nb_dest} — {cop['nom']}")
                    progress.empty()
                    if ok_list:
                        st.success(f"✅ {len(ok_list)} email(s) envoyé(s)")
                        with st.expander("Détail des envois"):
                            for l in ok_list: st.markdown(l)
                    if err_list:
                        st.error(f"❌ {len(err_list)} erreur(s)")
                        for l in err_list: st.markdown(l)

    # ══════════════════════════════════
    # 💬 WHATSAPP
    # ══════════════════════════════════
    elif canal == "💬 WhatsApp":
        st.info("💡 WhatsApp s'ouvre dans un nouvel onglet pour chaque destinataire. "
                "Validez l'envoi dans WhatsApp Web ou l'app.")

        if nb_dest > 0 and corps.strip():
            st.subheader("🔗 Liens WhatsApp")
            for _, cop in destinataires.iterrows():
                tel = str(cop.get('telephone','') or '').strip()
                # Normaliser le numéro : supprimer espaces, tirets, garder le +
                tel_clean = ''.join(c for c in tel if c.isdigit() or c == '+')
                if tel_clean.startswith('0'):
                    tel_clean = '+33' + tel_clean[1:]  # France par défaut
                tel_api = tel_clean.replace('+','')

                corps_perso = corps.replace("{nom}", cop['nom']) if personnaliser else corps
                msg_encode  = urllib.parse.quote(corps_perso)
                wa_link     = f"https://wa.me/{tel_api}?text={msg_encode}"

                col_wa1, col_wa2 = st.columns([3, 1])
                with col_wa1:
                    st.markdown(f"**Lot {int(cop.get('lot',0))}** — {cop['nom']} | 📱 {tel}")
                with col_wa2:
                    st.link_button(f"💬 Ouvrir WhatsApp", wa_link, use_container_width=True)

            st.divider()
            # Bouton "tout ouvrir" (JS)
            links_js = [
                f"https://wa.me/{''.join(c for c in str(r.get('telephone','') or '').replace(' ','') if c.isdigit() or c=='+').replace('+','').replace('0','33',1) if str(r.get('telephone','')).startswith('0') else ''.join(c for c in str(r.get('telephone','') or '').replace(' ','') if c.isdigit() or c=='+').replace('+','')}?text={urllib.parse.quote(corps.replace('{nom}', r['nom']) if personnaliser else corps)}"
                for _, r in destinataires.iterrows()
                if str(r.get('telephone','')).strip() not in ('','None','nan')
            ]
            if len(links_js) > 1:
                js_open = "; ".join([f"window.open('{l}','_blank')" for l in links_js[:10]])
                btn_html = (
                    '<button onclick="' + js_open + '" style="background:#25D366;color:white;'
                    'border:none;padding:10px 20px;border-radius:6px;cursor:pointer;'
                    'font-size:1em;width:100%;">💬 Ouvrir tous les WhatsApp ('
                    + str(min(len(links_js),10)) + ')</button>'
                )
                st.markdown(btn_html, unsafe_allow_html=True)
                if len(links_js) > 10:
                    st.warning("⚠️ Maximum 10 onglets simultanés. Envoyez par groupes.")
        else:
            if not corps.strip():
                st.warning("Rédigez un message avant d'envoyer.")

    # ══════════════════════════════════
    # 📱 SMS
    # ══════════════════════════════════
    else:  # SMS
        sms_tab1, sms_tab2 = st.tabs(["📋 Liens SMS (gratuit)", "🔌 Twilio API"])

        with sms_tab1:
            st.info("💡 Cliquez sur chaque lien pour ouvrir l'app SMS de votre appareil "
                    "(fonctionne mieux sur mobile).")
            if nb_dest > 0 and corps.strip():
                for _, cop in destinataires.iterrows():
                    tel = str(cop.get('telephone','') or '').strip()
                    corps_perso = corps.replace("{nom}", cop['nom']) if personnaliser else corps
                    sms_link = f"sms:{tel}?body={urllib.parse.quote(corps_perso)}"
                    col_s1, col_s2 = st.columns([3,1])
                    with col_s1:
                        st.markdown(f"**Lot {int(cop.get('lot',0))}** — {cop['nom']} | 📱 {tel}")
                    with col_s2:
                        st.link_button("📱 SMS", sms_link, use_container_width=True)

                # Numéros à copier en masse
                st.divider()
                st.markdown("**📋 Tous les numéros (à copier)**")
                numeros = ", ".join([
                    str(r.get('telephone','')) for _, r in destinataires.iterrows()
                    if str(r.get('telephone','')).strip() not in ('','None','nan')
                ])
                st.code(numeros)
            else:
                if not corps.strip():
                    st.warning("Rédigez un message avant d'envoyer.")

        with sms_tab2:
            st.markdown("#### 🔌 Envoi via Twilio")
            st.caption("Nécessite un compte Twilio (gratuit pour tester). "
                       "Configurez vos credentials dans Streamlit Secrets.")
            st.code("""[secrets]
twilio_account_sid = "ACxxxxxxxxxxxxxxxx"
twilio_auth_token  = "xxxxxxxxxxxxxxxx"
twilio_from_number = "+33xxxxxxxxx"
""", language="toml")

            try:
                twilio_sid  = st.secrets.get("twilio_account_sid","")
                twilio_tok  = st.secrets.get("twilio_auth_token","")
                twilio_from = st.secrets.get("twilio_from_number","")
            except:
                twilio_sid = twilio_tok = twilio_from = ""

            if not twilio_sid:
                twilio_sid  = st.text_input("Account SID",  type="password", key="tw_sid")
                twilio_tok  = st.text_input("Auth Token",   type="password", key="tw_tok")
                twilio_from = st.text_input("Numéro Twilio (format +33...)", key="tw_from")

            if st.button("📱 Envoyer les SMS via Twilio", type="primary",
                         disabled=(nb_dest == 0 or not corps.strip()),
                         use_container_width=True, key="btn_sms_twilio"):
                if not twilio_sid or not twilio_tok:
                    st.error("❌ Configurez Twilio avant d'envoyer.")
                else:
                    try:
                        from twilio.rest import Client as TwilioClient
                        client_tw = TwilioClient(twilio_sid, twilio_tok)
                        ok_sms, err_sms = [], []
                        prog_sms = st.progress(0, text="Envoi SMS…")
                        for i, (_, cop) in enumerate(destinataires.iterrows()):
                            tel = str(cop.get('telephone','') or '').strip()
                            tel_clean = ''.join(c for c in tel if c.isdigit() or c == '+')
                            if tel_clean.startswith('0'):
                                tel_clean = '+33' + tel_clean[1:]
                            corps_perso = corps.replace("{nom}", cop['nom']) if personnaliser else corps
                            try:
                                client_tw.messages.create(
                                    body=corps_perso, from_=twilio_from, to=tel_clean)
                                ok_sms.append(f"✅ {cop['nom']} ({tel})")
                            except Exception as e:
                                err_sms.append(f"❌ {cop['nom']} — {e}")
                            prog_sms.progress((i+1)/nb_dest)
                        prog_sms.empty()
                        if ok_sms:
                            st.success(f"✅ {len(ok_sms)} SMS envoyé(s)")
                            with st.expander("Détail"):
                                for l in ok_sms: st.markdown(l)
                        if err_sms:
                            st.error(f"❌ {len(err_sms)} erreur(s)")
                            for l in err_sms: st.markdown(l)
                    except ImportError:
                        st.error("❌ Package Twilio non installé. Ajoutez `twilio` dans requirements.txt")
                    except Exception as e:
                        st.error(f"❌ Erreur Twilio : {e}")


# ==================== LOCATAIRES ====================
elif menu == "🏠 Locataires":
    st.markdown("<h1 class='main-header'>🏠 Locataires</h1>", unsafe_allow_html=True)
    st.caption("Fiches locataires par copropriétaire — mise à jour boîtes aux lettres & interphone")

    @st.cache_data(ttl=30)
    def get_locataires():
        try:
            r = supabase.table('locataires').select('*').execute()
            return pd.DataFrame(r.data) if r.data else pd.DataFrame()
        except:
            return pd.DataFrame()

    copro_loc = get_coproprietaires()
    if copro_loc.empty:
        st.error("❌ Impossible de charger les copropriétaires."); st.stop()
    copro_loc = prepare_copro(copro_loc)
    loc_df    = get_locataires()

    # Normalisation
    if not loc_df.empty:
        loc_df['lot_id'] = pd.to_numeric(loc_df['lot_id'], errors='coerce')
    copro_loc['id'] = pd.to_numeric(copro_loc['id'], errors='coerce')

    EMOJI_USAGE = {
        'parking': '🅿️', 'studio': '🏠', 'studio ': '🏠',
        '2pieces': '🏠', '2 pieces': '🏠', '2 pieces duplex': '🏠',
        '3 pieces': '🏠', '3 pieces duplex': '🏠',
    }

    def usage_label(u):
        u = str(u or '').strip().lower()
        e = EMOJI_USAGE.get(u, '🏠')
        labels = {'parking':'Parking','studio':'Studio','studio ':'Studio',
                  '2pieces':'2 pièces','2 pieces':'2 pièces',
                  '2 pieces duplex':'2 pièces duplex','3 pieces':'3 pièces',
                  '3 pieces duplex':'3 pièces duplex'}
        return f"{e} {labels.get(u, u.title())}"

    loc_tab1, loc_tab2, loc_tab3, loc_tab4, loc_tab5 = st.tabs([
        "🏠 Fiches par propriétaire", "📋 Tous les locataires",
        "🏷️ BAL & Interphone", "📊 Statistiques", "📨 Envoyer les fiches"
    ])

    # ══════════════════════════════════════════════════════════════
    # TAB 1 — FICHES PAR PROPRIÉTAIRE
    # ══════════════════════════════════════════════════════════════
    with loc_tab1:
        # Grouper les lots par propriétaire (nom)
        noms_uniques = sorted(copro_loc['nom'].unique())

        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            sel_proprietaire = st.selectbox("👤 Sélectionner le propriétaire",
                                            noms_uniques, key="loc_prop_sel")
        with col_s2:
            st.metric("Propriétaires", len(noms_uniques))

        # Tous les lots de ce propriétaire
        lots_prop = copro_loc[copro_loc['nom'] == sel_proprietaire].sort_values('lot')

        st.divider()

        # En-tête fiche propriétaire
        nb_lots   = len(lots_prop)
        nb_appts  = len(lots_prop[~lots_prop['usage'].str.lower().str.contains('parking', na=False)])
        nb_pk     = len(lots_prop[lots_prop['usage'].str.lower().str.contains('parking', na=False)])

        h1, h2, h3, h4 = st.columns(4)
        h1.metric("👤 Propriétaire", sel_proprietaire.split('(')[0].strip())
        h2.metric("🔑 Lots total",   nb_lots)
        h3.metric("🏠 Appartements", nb_appts)
        h4.metric("🅿️ Parkings",    nb_pk)

        # Contact propriétaire (depuis coproprietaires)
        cop_row_contact = lots_prop.iloc[0]
        email_prop = cop_row_contact.get('email','') or ''
        tel_prop   = cop_row_contact.get('telephone','') or ''
        if email_prop or tel_prop:
            st.info(f"📧 {email_prop}   📱 {tel_prop}")

        st.divider()
        st.subheader("🏠 Lots & Locataires")

        # Pour chaque lot, afficher + éditer le locataire
        for _, lot_row in lots_prop.iterrows():
            lot_id   = int(lot_row['id'])
            lot_num  = lot_row.get('lot', '?')
            etage    = lot_row.get('etage', '?')
            usage    = lot_row.get('usage', '')
            desc     = lot_row.get('description', '') or ''

            # Locataire actif pour ce lot
            loc_actif = pd.DataFrame()
            if not loc_df.empty and 'lot_id' in loc_df.columns:
                loc_actif = loc_df[
                    (loc_df['lot_id'] == lot_id) &
                    (loc_df['actif'] == True)
                ]

            has_loc = not loc_actif.empty
            badge   = "✅ Loué" if has_loc else "⬜ Libre / Occupé propriétaire"
            color   = "#1a3a2a" if has_loc else "#2a2a2a"

            with st.expander(
                f"**Lot {lot_num}** — {usage_label(usage)} — Étage : {etage}  |  {badge}",
                expanded=True
            ):
                st.markdown(
                    f"<div style='background:{color};padding:8px 12px;border-radius:6px;"
                    f"margin-bottom:10px;font-size:0.9em;color:#ccc;'>"
                    f"🔑 Lot <b>{lot_num}</b> &nbsp;|&nbsp; {usage_label(usage)} "
                    f"&nbsp;|&nbsp; {etage} &nbsp;|&nbsp; {desc}</div>",
                    unsafe_allow_html=True
                )

                if has_loc:
                    loc_row = loc_actif.iloc[0]
                    loc_db_id = int(loc_row['id'])
                    col_inf, col_form = st.columns([1, 1])
                    with col_inf:
                        st.markdown(f"**Locataire actuel**")
                        st.markdown(f"👤 {loc_row.get('prenom','')} **{loc_row.get('nom','')}**")
                        if loc_row.get('email'):  st.markdown(f"📧 {loc_row['email']}")
                        if loc_row.get('telephone'): st.markdown(f"📱 {loc_row['telephone']}")
                        if loc_row.get('label_bal'): st.markdown(f"📬 BAL : *{loc_row['label_bal']}*")
                        if loc_row.get('label_interphone'): st.markdown(f"📞 Interphone : *{loc_row['label_interphone']}*")
                        if loc_row.get('date_entree'): st.markdown(f"📅 Entrée : {loc_row['date_entree']}")
                    with col_form:
                        with st.form(f"form_edit_loc_{loc_db_id}"):
                            st.markdown("**✏️ Modifier**")
                            e_prenom = st.text_input("Prénom", value=str(loc_row.get('prenom','') or ''), key=f"ep_{loc_db_id}")
                            e_nom    = st.text_input("Nom",    value=str(loc_row.get('nom','') or ''),    key=f"en_{loc_db_id}")
                            e_email  = st.text_input("Email",  value=str(loc_row.get('email','') or ''),  key=f"ee_{loc_db_id}")
                            e_tel    = st.text_input("Téléphone", value=str(loc_row.get('telephone','') or ''), key=f"et_{loc_db_id}")
                            e_bal    = st.text_input("Étiquette BAL",       value=str(loc_row.get('label_bal','') or ''), key=f"eb_{loc_db_id}")
                            e_iph    = st.text_input("Étiquette Interphone",value=str(loc_row.get('label_interphone','') or ''), key=f"ei_{loc_db_id}")
                            e_notes  = st.text_input("Notes", value=str(loc_row.get('notes','') or ''), key=f"eno_{loc_db_id}")
                            c1f, c2f = st.columns(2)
                            with c1f:
                                if st.form_submit_button("💾 Enregistrer", use_container_width=True, type="primary"):
                                    supabase.table('locataires').update({
                                        'prenom': e_prenom.strip() or None,
                                        'nom': e_nom.strip() or None,
                                        'email': e_email.strip() or None,
                                        'telephone': e_tel.strip() or None,
                                        'label_bal': e_bal.strip() or None,
                                        'label_interphone': e_iph.strip() or None,
                                        'notes': e_notes.strip() or None,
                                    }).eq('id', loc_db_id).execute()
                                    st.cache_data.clear(); st.rerun()
                            with c2f:
                                if st.form_submit_button("🚪 Départ", use_container_width=True):
                                    supabase.table('locataires').update({
                                        'actif': False,
                                        'date_sortie': pd.Timestamp.today().strftime('%Y-%m-%d')
                                    }).eq('id', loc_db_id).execute()
                                    st.cache_data.clear(); st.rerun()

                else:
                    # Formulaire ajout nouveau locataire
                    with st.form(f"form_new_loc_{lot_id}"):
                        st.markdown("**➕ Ajouter un locataire**")
                        n1, n2 = st.columns(2)
                        with n1:
                            n_prenom = st.text_input("Prénom",    key=f"np_{lot_id}")
                            n_nom    = st.text_input("Nom *",     key=f"nn_{lot_id}")
                            n_email  = st.text_input("Email",     key=f"ne_{lot_id}")
                        with n2:
                            n_tel    = st.text_input("Téléphone", key=f"nt_{lot_id}")
                            n_bal    = st.text_input("Étiquette BAL",       key=f"nb_{lot_id}",
                                                     placeholder=f"Ex: DUPONT - Lot {lot_num}")
                            n_iph    = st.text_input("Étiquette Interphone",key=f"ni_{lot_id}",
                                                     placeholder=f"Ex: DUPONT")
                        n_entree = st.date_input("Date d'entrée", key=f"nde_{lot_id}")
                        n_notes  = st.text_input("Notes",         key=f"nno_{lot_id}")
                        if st.form_submit_button("✅ Enregistrer le locataire",
                                                  use_container_width=True, type="primary"):
                            if not n_nom.strip():
                                st.error("❌ Le nom est obligatoire.")
                            else:
                                supabase.table('locataires').insert({
                                    'lot_id':    lot_id,
                                    'prenom':    n_prenom.strip() or None,
                                    'nom':       n_nom.strip(),
                                    'email':     n_email.strip() or None,
                                    'telephone': n_tel.strip() or None,
                                    'label_bal': n_bal.strip() or None,
                                    'label_interphone': n_iph.strip() or None,
                                    'date_entree': n_entree.strftime('%Y-%m-%d'),
                                    'notes':     n_notes.strip() or None,
                                    'actif':     True,
                                }).execute()
                                st.success(f"✅ Locataire enregistré pour le lot {lot_num}.")
                                st.cache_data.clear(); st.rerun()

    # ══════════════════════════════════════════════════════════════
    # TAB 2 — TOUS LES LOCATAIRES
    # ══════════════════════════════════════════════════════════════
    with loc_tab2:
        st.subheader("📋 Liste complète des locataires")

        if loc_df.empty:
            st.info("Aucun locataire enregistré.")
        else:
            # Joindre avec copropriétaires
            merged = loc_df.merge(
                copro_loc[['id','nom','lot','etage','usage']].rename(
                    columns={'id':'lot_id','nom':'proprietaire'}),
                on='lot_id', how='left'
            )

            # Filtres
            f1, f2, f3 = st.columns(3)
            with f1:
                filt_actif = st.radio("Statut", ["Actifs", "Tous", "Anciens"],
                                      horizontal=True, key="loc_filt_actif")
            with f2:
                filt_usage = st.selectbox("Usage", ["Tous"] + sorted(
                    copro_loc['usage'].dropna().unique().tolist()), key="loc_filt_usage")
            with f3:
                filt_search = st.text_input("🔍 Recherche", key="loc_search",
                                            placeholder="Nom locataire ou propriétaire…")

            df_show = merged.copy()
            if filt_actif == "Actifs":
                df_show = df_show[df_show['actif'] == True]
            elif filt_actif == "Anciens":
                df_show = df_show[df_show['actif'] != True]
            if filt_usage != "Tous":
                df_show = df_show[df_show['usage'] == filt_usage]
            if filt_search:
                mask = (
                    df_show['nom'].fillna('').str.contains(filt_search, case=False) |
                    df_show['prenom'].fillna('').str.contains(filt_search, case=False) |
                    df_show['proprietaire'].fillna('').str.contains(filt_search, case=False)
                )
                df_show = df_show[mask]

            # Métriques
            m1, m2, m3 = st.columns(3)
            m1.metric("Locataires actifs",  int((merged['actif']==True).sum()))
            m2.metric("Affichés",           len(df_show))
            m3.metric("Lots loués / Total", f"{int((merged['actif']==True).sum())} / 70")

            # Tableau
            cols_disp = {
                'lot': 'Lot', 'etage': 'Étage', 'usage': 'Usage',
                'proprietaire': 'Propriétaire',
                'prenom': 'Prénom loc.', 'nom': 'Nom loc.',
                'email': 'Email', 'telephone': 'Téléphone',
                'label_bal': 'BAL', 'label_interphone': 'Interphone',
                'date_entree': 'Entrée', 'actif': 'Actif'
            }
            cols_ok = [c for c in cols_disp if c in df_show.columns]
            df_tab  = df_show[cols_ok].copy()
            df_tab.columns = [cols_disp[c] for c in cols_ok]
            df_tab = df_tab.sort_values('Lot') if 'Lot' in df_tab.columns else df_tab

            st.dataframe(df_tab, use_container_width=True, hide_index=True, height=500,
                column_config={
                    'Actif': st.column_config.CheckboxColumn("Actif"),
                    'Lot':   st.column_config.NumberColumn("Lot", format="%d"),
                })

            csv_loc = df_tab.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button("📥 Exporter CSV", data=csv_loc,
                               file_name="locataires.csv", mime="text/csv", key="dl_loc")

    # ══════════════════════════════════════════════════════════════
    # TAB 3 — BAL & INTERPHONE
    # ══════════════════════════════════════════════════════════════
    with loc_tab3:
        st.subheader("🏷️ Étiquettes — Boîtes aux lettres & Interphone")
        st.caption("Vue synthétique pour mise à jour des étiquettes. "
                   "Affiche le nom du locataire s'il y en a un, sinon le propriétaire.")

        # Construire la liste complète lots + nom affiché
        rows_bal = []
        for _, lot in copro_loc.iterrows():
            lot_id_b = int(lot['id'])
            loc_actif_b = pd.DataFrame()
            if not loc_df.empty and 'lot_id' in loc_df.columns:
                loc_actif_b = loc_df[(loc_df['lot_id'] == lot_id_b) & (loc_df['actif'] == True)]

            if not loc_actif_b.empty:
                lr = loc_actif_b.iloc[0]
                nom_affiche  = f"{lr.get('prenom','')} {lr.get('nom','')}".strip()
                label_bal    = lr.get('label_bal','') or nom_affiche
                label_iph    = lr.get('label_interphone','') or nom_affiche.split()[-1] if nom_affiche else ''
                statut       = "🏠 Locataire"
            else:
                prop_name    = lot['nom'].split('(')[0].strip()
                nom_affiche  = prop_name
                label_bal    = prop_name
                label_iph    = prop_name.split()[-1] if prop_name else ''
                statut       = "👤 Propriétaire"

            is_parking = 'parking' in str(lot.get('usage','')).lower()
            rows_bal.append({
                'Lot':        int(lot.get('lot', 0)),
                'Étage':      lot.get('etage',''),
                'Usage':      usage_label(lot.get('usage','')),
                'Statut':     statut,
                'Nom affiché': nom_affiche,
                '📬 BAL':     label_bal,
                '📞 Interphone': '' if is_parking else label_iph,
                'Propriétaire': lot['nom'].split('(')[0].strip(),
            })

        df_bal = pd.DataFrame(rows_bal).sort_values('Lot')

        # Filtres
        bf1, bf2 = st.columns(2)
        with bf1:
            filt_bal_usage = st.radio("Afficher",
                ["Appartements + Studios", "Tous (+ parkings)"], horizontal=True, key="bal_filt")
        with bf2:
            filt_bal_statut = st.selectbox("Statut", ["Tous", "🏠 Locataire", "👤 Propriétaire"],
                                           key="bal_stat")

        df_bal_show = df_bal.copy()
        if filt_bal_usage == "Appartements + Studios":
            df_bal_show = df_bal_show[~df_bal_show['Usage'].str.contains('Parking', na=False)]
        if filt_bal_statut != "Tous":
            df_bal_show = df_bal_show[df_bal_show['Statut'] == filt_bal_statut]

        nb_loc_b = int((df_bal['Statut'] == '🏠 Locataire').sum())
        nb_prop_b = int((df_bal['Statut'] == '👤 Propriétaire').sum())
        b1, b2, b3 = st.columns(3)
        b1.metric("🏠 Locataires",    nb_loc_b)
        b2.metric("👤 Propriétaires", nb_prop_b)
        b3.metric("📊 Taux location", f"{nb_loc_b/len(df_bal)*100:.0f}%")

        st.dataframe(df_bal_show, use_container_width=True, hide_index=True,
            column_config={
                'Lot': st.column_config.NumberColumn("Lot", format="%d"),
            })

        # Export pour impression
        csv_bal = df_bal_show.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button("📥 Exporter liste BAL/Interphone", data=csv_bal,
                           file_name="bal_interphone.csv", mime="text/csv", key="dl_bal")

        # Vue impression étiquettes
        st.divider()
        st.subheader("🖨️ Aperçu étiquettes")
        st.caption("Format compact pour impression ou copier-coller")
        apts_only = df_bal_show[~df_bal_show['Usage'].str.contains('Parking', na=False)]
        html_tags = "<div style='display:flex;flex-wrap:wrap;gap:8px;'>"
        for _, r in apts_only.iterrows():
            bg = "#1a3a2a" if "Locataire" in r['Statut'] else "#1a1a2e"
            html_tags += (
                f"<div style='background:{bg};border:1px solid #444;border-radius:4px;"
                f"padding:8px 12px;min-width:160px;'>"
                f"<div style='font-size:0.75em;color:#888;'>Lot {r['Lot']} — {r['Étage']}</div>"
                f"<div style='font-weight:bold;color:#eee;font-size:0.95em;'>{r['📬 BAL']}</div>"
                f"<div style='font-size:0.75em;color:#aaa;'>{r['Statut']}</div>"
                f"</div>"
            )
        html_tags += "</div>"
        st.markdown(html_tags, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 5 — ENVOYER LES FICHES
    # ══════════════════════════════════════════════════════════════
    with loc_tab5:
        st.subheader("📨 Envoyer les fiches de renseignement")
        st.caption("Générez un lien unique par propriétaire et envoyez-le par email, WhatsApp ou SMS.")

        import hashlib as _hl
        import urllib.parse as _up2

        # URL de base de l'app
        try:
            _app_url = st.secrets.get("app_url", "")
        except:
            _app_url = ""

        _app_url_input = st.text_input(
            "🔗 URL de votre app Streamlit",
            value=_app_url or "https://votre-app.streamlit.app",
            key="app_url_input",
            help="Copiez l'URL complète de votre app depuis le navigateur"
        )
        if not _app_url_input.startswith("http"):
            st.warning("⚠️ Entrez l'URL complète (commençant par https://)")

        st.divider()

        # Sélection des propriétaires à contacter
        st.markdown("#### 👥 Sélection des propriétaires")
        _noms_all = sorted(copro_loc['nom'].unique())

        _mode_sel_f = st.radio("Sélection",
            ["✅ Tous les propriétaires", "🔍 Sélection manuelle"],
            horizontal=True, key="fiche_sel_mode")

        if _mode_sel_f == "🔍 Sélection manuelle":
            _sel_props = st.multiselect("Propriétaires", _noms_all, key="fiche_sel_props")
        else:
            _sel_props = _noms_all

        st.metric("📨 Fiches à envoyer", len(_sel_props))
        st.divider()

        # Personnalisation du message
        st.markdown("#### ✍️ Message d'accompagnement")
        _canal_f = st.radio("Canal", ["📧 Email", "💬 WhatsApp", "📱 SMS"],
                            horizontal=True, key="fiche_canal")

        _msg_defaut = """Bonjour {nom},

Dans le cadre de la mise à jour de notre annuaire (boîtes aux lettres et interphone), merci de bien vouloir remplir la fiche ci-dessous :

🔗 {lien}

Cette démarche ne prend que 2 minutes.

Merci de votre collaboration.
Cordialement,
Le Syndic"""

        _msg_template = st.text_area("Message (utilisez {nom} et {lien})",
            value=_msg_defaut, height=200, key="fiche_msg")

        if _canal_f == "📧 Email":
            _sujet_f = st.text_input("Objet de l'email",
                value="📋 Mise à jour annuaire — Fiche locataire à remplir",
                key="fiche_sujet")

        st.divider()

        # Génération et envoi
        if st.button("🚀 Générer les liens et envoyer", type="primary",
                     use_container_width=True, key="btn_send_fiches",
                     disabled=not _sel_props):

            _brevo_key_f  = ""
            _brevo_from_f = ""
            _brevo_name_f = "Syndic Copropriété"
            try:
                _brevo_key_f  = st.secrets.get("brevo_api_key","")
                _brevo_from_f = st.secrets.get("brevo_from_email","")
                _brevo_name_f = st.secrets.get("brevo_from_name","Syndic Copropriété")
            except:
                pass

            import urllib.request as _ureq3, json as _j3, uuid as _uuid3
            _today_str = pd.Timestamp.today().strftime('%Y-%m-%d')

            _progress_f = st.progress(0, text="Génération des liens…")
            _ok_f, _err_f, _liens_generes = [], [], []

            for _i_f, _nom_prop in enumerate(_sel_props):
                # Récupérer le contact du propriétaire
                _rows_p = copro_loc[copro_loc['nom'] == _nom_prop]
                if _rows_p.empty:
                    _err_f.append(f"❌ {_nom_prop} — introuvable")
                    continue
                _row_p  = _rows_p.iloc[0]
                _email_p = str(_row_p.get('email','') or '').strip()
                _tel_p   = str(_row_p.get('telephone','') or '').strip()

                # Générer un token unique
                _token_val = _uuid3.uuid4().hex

                # Stocker dans fiches_tokens
                try:
                    # Désactiver les anciens tokens pour ce propriétaire
                    supabase.table('fiches_tokens').update(
                        {'actif': False}
                    ).eq('proprietaire_nom', _nom_prop).execute()

                    # Créer le nouveau token
                    supabase.table('fiches_tokens').insert({
                        'token':            _token_val,
                        'proprietaire_nom': _nom_prop,
                        'actif':            True,
                        'utilise':          False,
                        'created_at':       _today_str,
                    }).execute()
                except Exception as _e_tok:
                    _err_f.append(f"❌ {_nom_prop} — erreur token: {_e_tok}")
                    continue

                # Construire le lien
                _lien_f = f"{_app_url_input.rstrip('/')}?fiche={_token_val}"
                _liens_generes.append({'Propriétaire': _nom_prop, 'Lien': _lien_f,
                                       'Email': _email_p, 'Tel': _tel_p})

                # Personnaliser le message
                _nom_court = _nom_prop.split('(')[0].strip()
                _msg_perso = _msg_template.replace('{nom}', _nom_court).replace('{lien}', _lien_f)

                # Envoi selon canal
                if _canal_f == "📧 Email":
                    if not _email_p or _email_p in ('None','nan'):
                        _err_f.append(f"⚠️ {_nom_prop} — pas d'email")
                    elif not _brevo_key_f:
                        _err_f.append(f"⚠️ {_nom_prop} — Brevo non configuré, lien généré uniquement")
                    else:
                        try:
                            _html_f = _msg_perso.replace("\n","<br>")
                            _pl_f = _j3.dumps({
                                "sender": {"name": _brevo_name_f, "email": _brevo_from_f},
                                "to": [{"email": _email_p, "name": _nom_court}],
                                "subject": _sujet_f,
                                "textContent": _msg_perso,
                                "htmlContent": f"<html><body style='font-family:Arial'><p>{_html_f}</p></body></html>",
                            }).encode('utf-8')
                            _req_f = _ureq3.Request("https://api.brevo.com/v3/smtp/email",
                                data=_pl_f,
                                headers={"accept":"application/json",
                                         "content-type":"application/json",
                                         "api-key":_brevo_key_f}, method="POST")
                            _ureq3.urlopen(_req_f)
                            _ok_f.append(f"✅ {_nom_prop} ({_email_p})")
                        except Exception as _e_br:
                            _err_f.append(f"❌ {_nom_prop} — {_e_br}")
                else:
                    # WhatsApp / SMS : liens générés, pas d'envoi automatique
                    _ok_f.append(f"🔗 {_nom_prop} — lien généré")

                _progress_f.progress((_i_f+1)/len(_sel_props),
                                     text=f"{_i_f+1}/{len(_sel_props)} — {_nom_prop[:30]}")

            _progress_f.empty()

            # Résultats
            if _ok_f:
                st.success(f"✅ {len(_ok_f)} fiche(s) traitée(s)")
                with st.expander("Détail"):
                    for _l in _ok_f: st.markdown(_l)

            if _err_f:
                st.warning(f"⚠️ {len(_err_f)} avertissement(s)")
                for _l in _err_f: st.markdown(_l)

            # Tableau des liens générés (pour WhatsApp/SMS ou backup)
            if _liens_generes:
                st.divider()
                st.markdown("#### 🔗 Liens générés")
                df_liens = pd.DataFrame(_liens_generes)

                if _canal_f in ("💬 WhatsApp", "📱 SMS"):
                    st.info("Cliquez sur chaque lien pour l'envoyer manuellement.")
                    for _, _lr in df_liens.iterrows():
                        _nom_c  = _lr['Propriétaire'].split('(')[0].strip()
                        _tel_c  = str(_lr.get('Tel','') or '').strip()
                        _msg_wa = _msg_template.replace('{nom}', _nom_c).replace('{lien}', _lr['Lien'])
                        _col_a, _col_b = st.columns([3,1])
                        with _col_a:
                            st.markdown(f"**{_lr['Propriétaire']}** | 📱 {_tel_c}")
                            st.code(_lr['Lien'], language=None)
                        with _col_b:
                            if _canal_f == "💬 WhatsApp" and _tel_c:
                                _tel_wa = ''.join(c for c in _tel_c if c.isdigit() or c=='+')
                                if _tel_wa.startswith('0'): _tel_wa = '33' + _tel_wa[1:]
                                _tel_wa = _tel_wa.replace('+','')
                                _wa_lien = f"https://wa.me/{_tel_wa}?text={_up2.quote(_msg_wa)}"
                                st.link_button("💬 WhatsApp", _wa_lien, use_container_width=True)
                            elif _canal_f == "📱 SMS" and _tel_c:
                                _sms_lien = f"sms:{_tel_c}?body={_up2.quote(_msg_wa)}"
                                st.link_button("📱 SMS", _sms_lien, use_container_width=True)

                # Export CSV des liens
                csv_liens = df_liens.to_csv(index=False, sep=';').encode('utf-8-sig')
                st.download_button("📥 Exporter les liens CSV", data=csv_liens,
                                   file_name="fiches_liens.csv", mime="text/csv", key="dl_liens")

        # ══════════════════════════════════════════════════════════════
    # TAB 4 — STATISTIQUES
    # ══════════════════════════════════════════════════════════════
    with loc_tab4:
        st.subheader("📊 Statistiques occupation")

        nb_appts_total = len(copro_loc[~copro_loc['usage'].str.lower().str.contains('parking', na=False)])
        nb_pk_total    = len(copro_loc[copro_loc['usage'].str.lower().str.contains('parking', na=False)])
        nb_loc_actifs  = 0 if loc_df.empty else int((loc_df['actif'] == True).sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏠 Lots habitation",  nb_appts_total)
        c2.metric("🅿️ Parkings",        nb_pk_total)
        c3.metric("🏠 Lots loués",       nb_loc_actifs)
        c4.metric("📊 Taux loc. global", f"{nb_loc_actifs/max(nb_appts_total,1)*100:.0f}%")

        st.divider()

        # Lots sans info locataire
        lots_sans_loc = []
        for _, lot in copro_loc[~copro_loc['usage'].str.lower().str.contains('parking', na=False)].iterrows():
            lid = int(lot['id'])
            has = not loc_df.empty and 'lot_id' in loc_df.columns and                   not loc_df[(loc_df['lot_id']==lid) & (loc_df['actif']==True)].empty
            if not has:
                lots_sans_loc.append({
                    'Lot': int(lot['lot']), 'Étage': lot['etage'],
                    'Usage': usage_label(lot['usage']),
                    'Propriétaire': lot['nom'].split('(')[0].strip(),
                    'Email prop.': lot.get('email','') or '—',
                })

        if lots_sans_loc:
            st.markdown(f"#### ⚠️ {len(lots_sans_loc)} lot(s) sans information locataire")
            st.caption("Ces lots sont occupés par leur propriétaire ou l'information n'a pas été saisie.")
            df_sans = pd.DataFrame(lots_sans_loc).sort_values('Lot')
            st.dataframe(df_sans, use_container_width=True, hide_index=True,
                column_config={'Lot': st.column_config.NumberColumn("Lot", format="%d")})
        else:
            st.success("✅ Tous les lots ont une information locataire !")


st.divider()
st.markdown("<div style='text-align: center; color: #666;'>🏢 Gestion de Copropriété — v2.0</div>", unsafe_allow_html=True)
