import os
import sys
import glob
import io
import argparse
import openai
import time
import fitz  # PyMuPDF
from xml.dom import minidom
import dicttoxml
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from PIL import Image

# Load environment variables from .env file
load_dotenv()
# OpenAIのAPIキー
openai.api_key = os.getenv('OPENAI_API_KEY')

prompt = """与えられた論文の要点をまとめ、以下の項目で日本語で出力せよ。それぞれの項目は最大でも180文字以内に要約せよ。
```
論文名:タイトルの日本語訳
キーワード:この論文のキーワード
課題:この論文が解決する課題
手法:この論文が提案する手法
結果:提案手法によって得られた結果
```"""

def get_summary(metadata):
    title = metadata['title']
    if isinstance(title, list):
        title = ''.join(title)
    
    text = f"title: {title}\nbody: {metadata.get('abstract', 'N/A')}"
    print("### input text", text)
    
    response = openai.ChatCompletion.create(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': text}
                ],
                temperature=0.25,
            )
    
    summary = response['choices'][0]['message']['content']
    print("#### GPT", summary)
    
    summary_dict = {}
    for line in summary.split('\n'):
        if line.startswith("論文名"):
            summary_dict['title_jp'] = line[4:].strip()
        elif line.startswith("キーワード"):
            summary_dict['keywords'] = line[6:].strip()
        elif line.startswith("課題"):
            summary_dict['problem'] = line[3:].strip()
        elif line.startswith("手法"):
            summary_dict['method'] = line[3:].strip()
        elif line.startswith("結果"):
            summary_dict['result'] = line[3:].strip()
    
    # Check for missing fields and handle errors
    required_fields = ['title_jp', 'keywords', 'problem', 'method', 'result']
    for field in required_fields:
        if field not in summary_dict:
            print(f"Warning: Missing field {field} in summary")
            summary_dict[field] = "N/A"  # or some other default value
    
    print("Dict by ChatGPT", summary_dict)
    return summary_dict

def recoverpix(doc, item):
    xref = item[0]
    smask = item[1]

    if smask > 0:
        pix0 = fitz.Pixmap(doc.extract_image(xref)["image"])
        if pix0.alpha:
            pix0 = fitz.Pixmap(pix0, 0)
        mask = fitz.Pixmap(doc.extract_image(smask)["image"])

        try:
            pix = fitz.Pixmap(pix0, mask)
        except:
            pix = fitz.Pixmap(doc.extract_image(xref)["image"])

        ext = "pam" if pix0.n > 3 else "png"
        return {"ext": ext, "colorspace": pix.colorspace.n, "image": pix.tobytes(ext)}

    if "/ColorSpace" in doc.xref_object(xref, compressed=True):
        pix = fitz.Pixmap(doc, xref)
        pix = fitz.Pixmap(fitz.csRGB, pix)
        return {"ext": "png", "colorspace": 3, "image": pix.tobytes("png")}

    return doc.extract_image(xref)

def extract_images_from_pdf(pdf_path, imgdir="./output", min_width=400, min_height=400, relsize=0.05, abssize=2048, max_ratio=8, max_num=5):
    if not os.path.exists(imgdir):
        os.makedirs(imgdir)

    t0 = time.time()
    doc = fitz.open(pdf_path)
    page_count = doc.page_count

    xreflist = []
    imglist = []
    images = []
    for pno in range(page_count):
        if len(images) >= max_num:
            break
        print(f"extract images {pno+1}/{page_count}")
        il = doc.get_page_images(pno)
        imglist.extend([x[0] for x in il])
        for img in il:
            xref = img[0]
            if xref in xreflist:
                continue
            width = img[2]
            height = img[3]
            print(f"{width}x{height}")
            if width < min_width and height < min_height:
                continue
            image = recoverpix(doc, img)
            n = image["colorspace"]
            imgdata = image["image"]

            if len(imgdata) <= abssize:
                continue

            if width / height > max_ratio or height/width > max_ratio:
                print(f"max_ratio {width/height} {height/width} {max_ratio}")
                continue

            print("*")

            imgname = f"img{pno+1:02d}_{xref:05d}.{image['ext']}"
            images.append((imgname, pno+1, width, height))
            imgfile = os.path.join(imgdir, imgname)
            with open(imgfile, "wb") as fout:
                fout.write(imgdata)
            xreflist.append(xref)

    t1 = time.time()
    imglist = list(set(imglist))
    print(len(set(imglist)), "images in total")
    print(len(xreflist), "images extracted")
    print("total time %g sec" % (t1 - t0))
    return xreflist, imglist, images

def get_half(fname, imgdir):
    pdf_file = fitz.open(fname)
    page = pdf_file[0]
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)
    im = Image.open(io.BytesIO(pix.tobytes()))
    width, height = im.size
    box = (0, height // 20, width, (height // 2) + (height // 20))
    im_cropped = im.crop(box)
    half_img_path = os.path.join(imgdir, "half.png")
    im_cropped.save(half_img_path, "PNG")
    return half_img_path


def get_metadata_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"File {pdf_path} does not exist。")
        return None

    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        
        if reader.is_encrypted:
            try:
                reader.decrypt('')
            except:
                print(f"Failed to decrypt {pdf_path}")
                return None
        
        info = reader.metadata
        metadata = {}
        
        # Extract available metadata fields
        if info.title:
            # Ensure title is a string and not a list of single characters
            if isinstance(info.title, list):
                metadata['title'] = ''.join(info.title)
            else:
                metadata['title'] = info.title
        else:
            metadata['title'] = "Unknown"
        
        if info.author:
            metadata['authors'] = info.author.split(',')
        else:
            metadata['authors'] = ["Unknown"]

        if info.subject:
            metadata['subject'] = info.subject
        else:
            metadata['subject'] = "N/A"
        
        if info.producer:
            metadata['producer'] = info.producer
        if info.creation_date:
            metadata['creation_date'] = info.creation_date
        if info.modification_date:
            metadata['mod_date'] = info.modification_date

        # Extract text from the first few pages as abstract
        text = ""
        for page_num in range(min(3, len(reader.pages))):  # Extract from first 3 pages or less if fewer pages
            text += reader.pages[page_num].extract_text()
        metadata['abstract'] = text[:2000]  # Limit to the first 2000 characters

        metadata['pdf_path'] = pdf_path

        return metadata


def get_paper_info(pdf_path, metadata, dirpath="./xmls"):
    paper_info = {
        'title': metadata['title'],
        'authors': metadata['authors'],
        'abstract': metadata.get('abstract', 'N/A'),
        'pdf': pdf_path
    }
    
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)

    # Extract images from the PDF
    images_dir = os.path.join(dirpath, "images")
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)

    image_count = extract_images_from_pdf(pdf_path, images_dir)
    paper_info['image_count'] = image_count
    paper_info['images'] = [os.path.join(images_dir, f) for f in os.listdir(images_dir)]

    half_img_path = get_half(pdf_path, images_dir)
    paper_info['half_img_path'] = half_img_path

    # Assuming get_summary can be called with title and abstract directly
    summary_info = get_summary(metadata)
    combined_info = {'paper': {**paper_info, **summary_info}}
    
    return combined_info

def convert_lists_to_strings(d):
    """Recursively convert lists of single characters to strings and handle special types."""
    from PyPDF2.generic import TextStringObject
    
    if isinstance(d, dict):
        for key, value in d.items():
            if isinstance(value, list) and all(isinstance(i, str) for i in value):
                d[key] = ''.join(value)
            elif isinstance(value, TextStringObject):
                d[key] = str(value)
            elif isinstance(value, list):
                d[key] = [convert_lists_to_strings(item) for item in value]
            else:
                d[key] = convert_lists_to_strings(value)
    elif isinstance(d, list) and all(isinstance(i, str) for i in d):
        d = ''.join(d)
    elif isinstance(d, list):
        d = [convert_lists_to_strings(item) for item in d]
    elif isinstance(d, TextStringObject):
        d = str(d)
    return d

def save_as_xml(data, filepath):
    # Convert lists of single characters to strings
    data = convert_lists_to_strings(data)
    
    # Generate XML content
    xml_content = dicttoxml.dicttoxml(data, attr_type=False, root=False).decode('utf-8')
    
    # Pretty print the XML
    pretty_xml = minidom.parseString(xml_content).toprettyxml(indent="   ")
    
    # Write to file
    with open(filepath, "w") as xml_file:
        xml_file.write(pretty_xml)

def main(pdf_dir=None, pdf_file=None, dir='./xmls'):
    pdf_files = []
    if pdf_file:
        pdf_files.append(pdf_file)
    elif pdf_dir:
        pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))

    if not pdf_files:
        print("#### No PDF files found in the specified location")
        sys.exit()
    
    if not os.path.exists(dir):
        os.makedirs(dir)
    
    for pdf_path in pdf_files:
        try:
            metadata = get_metadata_from_pdf(pdf_path)
            if metadata is None:
                continue
            entry_id = os.path.splitext(os.path.basename(pdf_path))[0]
            dirpath = os.path.join(dir, entry_id)
            paper_info = get_paper_info(pdf_path, metadata, dirpath=dirpath)
            paper_info['paper']['query'] = "N/A"  # Query is not applicable in this case

            save_as_xml(paper_info, os.path.join(dirpath, "paper.xml"))
        except Exception as e:
            print("Exception occurred:", e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_file', "-f", type=str, required=True, help='single PDF file to process')
    parser.add_argument('--dir', "-d", type=str, help='destination directory', default='./xmls')
    args = parser.parse_args()

    print(args)

    main(pdf_file=args.pdf_file, dir=args.dir)