from flask import Flask, render_template, request, send_file
import PyPDF2
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import re
import io
import zipfile
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

def extract_text_from_pdf(pdf_file):
    """استخراج النص من PDF باستخدام OCR"""
    try:
        # محاولة استخراج النص مباشرة
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        full_text = ""
        
        for page in pdf_reader.pages:
            full_text += page.extract_text() + "\n"
        
        # إذا كان النص فارغاً أو قليلاً، استخدم OCR
        if len(full_text.strip()) < 50:
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            for image in images:
                text = pytesseract.image_to_string(image, lang='ara+eng')
                full_text += text + "\n"
        
        return full_text
    except Exception as e:
        print(f"خطأ في استخراج النص: {str(e)}")
        return ""

def extract_waybill_number(text):
    """استخراج رقم البوليصة (3 حروف + 7 أرقام)"""
    # البحث عن النمط: ABC1234567
    pattern = r'[A-Z]{3}\d{7}'
    matches = re.findall(pattern, text)
    
    if matches:
        return matches[0]
    
    # محاولة ثانية: البحث عن أرقام متتالية
    digit_pattern = r'\d{7,}'
    digit_matches = re.findall(digit_pattern, text)
    
    if digit_matches:
        return digit_matches[0][:7]
    
    return None

def split_pdf_by_waybill(pdf_file):
    """فصل ملف PDF حسب رقم البوليصة"""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    waybill_pages = {}
    
    # قراءة كل صفحة واستخراج رقم البوليصة
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text = page.extract_text()
        
        # إذا كان النص قليلاً، استخدم OCR
        if len(text.strip()) < 100:
            try:
                pdf_file.seek(0)
                images = convert_from_bytes(pdf_file.read(), dpi=200)
                if page_num < len(images):
                    image = images[page_num]
                    text += pytesseract.image_to_string(image, lang='ara+eng')
            except:
                pass
        
        # استخراج رقم البوليصة
        waybill = extract_waybill_number(text)
        
        if waybill:
            if waybill not in waybill_pages:
                waybill_pages[waybill] = []
            waybill_pages[waybill].append(page_num)
    
    return waybill_pages, pdf_reader

def create_pdfs_from_pages(pdf_reader, waybill_pages):
    """إنشاء ملفات PDF منفصلة"""
    pdfs = {}
    
    for waybill, page_nums in waybill_pages.items():
        pdf_writer = PyPDF2.PdfWriter()
        
        # إضافة كل الصفحات الخاصة بهذه البوليصة
        for page_num in page_nums:
            pdf_writer.add_page(pdf_reader.pages[page_num])
        
        # حفظ في ذاكرة (BytesIO)
        pdf_bytes = io.BytesIO()
        pdf_writer.write(pdf_bytes)
        pdf_bytes.seek(0)
        
        pdfs[f"{waybill}.pdf"] = pdf_bytes
    
    return pdfs

def create_zip_file(pdfs):
    """إنشاء ملف ZIP من ملفات PDF"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, pdf_bytes in pdfs.items():
            zip_file.writestr(filename, pdf_bytes.getvalue())
    
    zip_buffer.seek(0)
    return zip_buffer

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        # التحقق من وجود الملف
        if 'file' not in request.files:
            return {'error': 'لم يتم اختيار ملف'}, 400
        
        file = request.files['file']
        
        if file.filename == '':
            return {'error': 'لم يتم اختيار ملف'}, 400
        
        if not file.filename.lower().endswith('.pdf'):
            return {'error': 'الملف يجب أن يكون PDF'}, 400
        
        # قراءة ملف PDF
        pdf_file = io.BytesIO(file.read())
        
        # فصل ملفات PDF حسب البوليصة
        waybill_pages, pdf_reader = split_pdf_by_waybill(pdf_file)
        
        if not waybill_pages:
            return {'error': 'لم يتم العثور على أي رقم بوليصة في المل��'}, 400
        
        # إنشاء ملفات PDF منفصلة
        pdfs = create_pdfs_from_pages(pdf_reader, waybill_pages)
        
        # إنشاء ملف ZIP
        zip_file = create_zip_file(pdfs)
        
        return send_file(
            zip_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='waybills.zip'
        )
    
    except Exception as e:
        return {'error': f'خطأ في معالجة الملف: {str(e)}'}, 500

if __name__ == '__main__':
    app.run(debug=False)
