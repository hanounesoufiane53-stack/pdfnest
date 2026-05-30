from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, uuid, zipfile
from pathlib import Path
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("outputs")
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

def save_upload(file):
    uid = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    path = UPLOAD_FOLDER / f"{uid}_{filename}"
    file.save(path)
    return path

def out(name):
    return OUTPUT_FOLDER / f"{str(uuid.uuid4())}_{name}"

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/api/status')
def status():
    return jsonify({"status": "running"})

@app.route('/api/merge', methods=['POST'])
def merge_pdf():
    try:
        from PyPDF2 import PdfMerger
        files = request.files.getlist('files')
        if len(files) < 2:
            return jsonify({"error": "Upload at least 2 PDFs"}), 400
        merger = PdfMerger()
        saved = []
        for f in files:
            p = save_upload(f); saved.append(p); merger.append(str(p))
        o = out("merged.pdf"); merger.write(str(o)); merger.close()
        for p in saved: p.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-merged.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/split', methods=['POST'])
def split_pdf():
    try:
        from PyPDF2 import PdfReader, PdfWriter
        file = request.files.get('file')
        page_range = request.form.get('range', '')
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        reader = PdfReader(str(path))
        total = len(reader.pages)
        pages = set()
        if page_range:
            for part in page_range.split(','):
                part = part.strip()
                if '-' in part:
                    a,b = part.split('-'); pages.update(range(int(a)-1,int(b)))
                else: pages.add(int(part)-1)
        else: pages = set(range(total))
        zip_out = out("split.zip")
        with zipfile.ZipFile(zip_out,'w') as zf:
            for i in sorted(pages):
                if 0<=i<total:
                    w=PdfWriter(); w.add_page(reader.pages[i])
                    pf=out(f"page_{i+1}.pdf")
                    with open(pf,'wb') as f2: w.write(f2)
                    zf.write(pf,f"page_{i+1}.pdf"); pf.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        return send_file(zip_out, as_attachment=True, download_name="pdfnest-split.zip")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/compress', methods=['POST'])
def compress_pdf():
    try:
        import fitz
        file = request.files.get('file')
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        doc = fitz.open(str(path))
        o = out("compressed.pdf")
        doc.save(str(o), garbage=4, deflate=True, clean=True)
        doc.close(); path.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-compressed.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pdf2word', methods=['POST'])
def pdf_to_word():
    try:
        from pdf2docx import Converter
        file = request.files.get('file')
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        o = out("converted.docx")
        cv = Converter(str(path)); cv.convert(str(o)); cv.close()
        path.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-converted.docx")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pdf2jpg', methods=['POST'])
def pdf_to_jpg():
    try:
        import fitz
        file = request.files.get('file')
        dpi = int(request.form.get('dpi', 150))
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        doc = fitz.open(str(path))
        zip_out = out("images.zip")
        with zipfile.ZipFile(zip_out,'w') as zf:
            for i, page in enumerate(doc):
                mat = fitz.Matrix(dpi/72, dpi/72)
                pix = page.get_pixmap(matrix=mat)
                ip = out(f"page_{i+1}.jpg"); pix.save(str(ip))
                zf.write(ip, f"page_{i+1}.jpg"); ip.unlink(missing_ok=True)
        doc.close(); path.unlink(missing_ok=True)
        return send_file(zip_out, as_attachment=True, download_name="pdfnest-images.zip")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/jpg2pdf', methods=['POST'])
def jpg_to_pdf():
    try:
        import fitz
        files = request.files.getlist('files')
        if not files: return jsonify({"error": "No files"}), 400
        doc = fitz.open(); saved = []
        for f in files:
            p = save_upload(f); saved.append(p)
            img = fitz.open(str(p))
            pdf_bytes = img.convert_to_pdf(); img.close()
            img_pdf = fitz.open("pdf", pdf_bytes)
            doc.insert_pdf(img_pdf)
        o = out("images.pdf"); doc.save(str(o)); doc.close()
        for p in saved: p.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-images.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rotate', methods=['POST'])
def rotate_pdf():
    try:
        import fitz
        file = request.files.get('file')
        angle = int(request.form.get('angle', 90))
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        doc = fitz.open(str(path))
        for page in doc: page.set_rotation(angle)
        o = out("rotated.pdf"); doc.save(str(o)); doc.close()
        path.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-rotated.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/protect', methods=['POST'])
def protect_pdf():
    try:
        import fitz
        file = request.files.get('file')
        password = request.form.get('password','')
        if not file: return jsonify({"error": "No file"}), 400
        if not password: return jsonify({"error": "No password"}), 400
        path = save_upload(file)
        doc = fitz.open(str(path)); o = out("protected.pdf")
        perm = fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY
        doc.save(str(o), encryption=fitz.PDF_ENCRYPT_AES_256,
                 user_pw=password, owner_pw=password+"_owner", permissions=perm)
        doc.close(); path.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-protected.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/unlock', methods=['POST'])
def unlock_pdf():
    try:
        import fitz
        file = request.files.get('file')
        password = request.form.get('password','')
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        doc = fitz.open(str(path))
        if doc.needs_pass:
            if not doc.authenticate(password):
                return jsonify({"error": "Wrong password"}), 400
        o = out("unlocked.pdf")
        doc.save(str(o), encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close(); path.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-unlocked.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/watermark', methods=['POST'])
def watermark_pdf():
    try:
        import fitz
        file = request.files.get('file')
        text = request.form.get('text','CONFIDENTIAL')
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        doc = fitz.open(str(path))
        for page in doc:
            rect = page.rect
            page.insert_text(fitz.Point(rect.width/2-100, rect.height/2),
                text, fontsize=48, color=(0.8,0.8,0.8), rotate=45)
        o = out("watermarked.pdf"); doc.save(str(o)); doc.close()
        path.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-watermarked.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-pages', methods=['POST'])
def delete_pages():
    try:
        import fitz
        file = request.files.get('file')
        page_range = request.form.get('range','')
        if not file: return jsonify({"error": "No file"}), 400
        path = save_upload(file)
        doc = fitz.open(str(path)); total = doc.page_count
        pages = set()
        if page_range:
            for part in page_range.split(','):
                part = part.strip()
                if '-' in part:
                    a,b = part.split('-'); pages.update(range(int(a)-1,int(b)))
                else: pages.add(int(part)-1)
        for i in sorted(pages, reverse=True):
            if 0<=i<total: doc.delete_page(i)
        o = out("result.pdf"); doc.save(str(o)); doc.close()
        path.unlink(missing_ok=True)
        return send_file(o, as_attachment=True, download_name="pdfnest-result.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/qrcode', methods=['POST'])
def generate_qr():
    try:
        import qrcode
        data = request.form.get('text','')
        if not data: return jsonify({"error": "No text"}), 400
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        o = out("qrcode.png"); img.save(str(o))
        return send_file(o, as_attachment=True, download_name="pdfnest-qrcode.png")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import threading, time
def cleanup():
    while True:
        time.sleep(3600)
        for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            for f in folder.iterdir():
                try:
                    if time.time() - f.stat().st_mtime > 7200: f.unlink()
                except: pass
threading.Thread(target=cleanup, daemon=True).start()

if __name__ == '__main__':
    print("\n========================================")
    print("  PDFnest is running!")
    print("  Open Chrome and go to:")
    print("  http://localhost:5000")
    print("========================================\n")
    app.run(debug=False, port=5000)
