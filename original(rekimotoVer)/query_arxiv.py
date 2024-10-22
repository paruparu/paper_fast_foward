import os
import glob
import argparse
import xmltodict
from PIL import Image
import re

def safe_filename(filename):
    """Generate a safe filename by removing or replacing invalid characters."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', filename)

def make_md(dirname, filename, keywords=[], min_size_kb=100):
    path = f"{dirname}/{filename}"
    with open(path, "r") as fin:
        xml = fin.read()
        xml_lower = xml.lower()
        print(f"Processing file: {filename}")
        
        # キーワードが指定されていない場合も処理を継続
        if keywords and not any([k.lower() in xml_lower for k in keywords]):
            print(f"Skipping file: {filename} (does not match keywords)")
            return None  # No output if keywords do not match
            
    dict = xmltodict.parse(xml)['paper']
    print(dict)

    # 変更点：キーが存在しない場合のデフォルト値を設定
    title_jp = dict.get('title_jp', 'N/A')
    title = dict.get('title', 'N/A')
    year = dict.get('year', 'N/A')
    keywords = dict.get('keywords', 'N/A')
    entry_id = dict.get('entry_id', 'N/A')
    problem = dict.get('problem', 'N/A')
    method = dict.get('method', 'N/A')
    result = dict.get('result', 'N/A')
    half_img_path = dict['half_img_path']

    # Generate safe output filename
    safe_title = safe_filename(title[:14])
    output_filename = f"{safe_title}_output.md"
    output_path = os.path.join(dirname, output_filename)

    with open(output_path, "w") as f:
        f.write('\n---\n')
        f.write('<!-- _class: title -->\n')
        f.write(f"# {title_jp}\n")
        f.write(f"{title}\n")
        f.write(f"[{year}] {keywords} {entry_id}\n") 
        f.write(f"__課題__ {problem}\n")
        f.write(f"__手法__ {method}\n")
        f.write(f"__結果__ {result}\n")

        f.write("\n---\n")
        f.write('<!-- _class: info -->\n') 
        f.write(f'![width:1400]({half_img_path})\n')

        # get images
        images_dir = os.path.join(dirname, "images")
        images = [f for f in os.listdir(images_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        images.remove('half.png') if 'half.png' in images else None  # Ensure half.png is not repeated

        # 画像ファイルサイズでフィルタリング
        valid_images = []
        for img in images:
            img_path = os.path.join(images_dir, img)
            img_size_kb = os.path.getsize(img_path) / 1024
            print(f"Image: {img}, Size: {img_size_kb:.2f} KB")  # デバッグ出力

            if img_size_kb > min_size_kb:  # サイズがmin_size_kb KBより大きい画像のみを選択
                valid_images.append(img)

        for img in valid_images:
            img_path = os.path.join(images_dir, img)
            with Image.open(img_path) as image:
                width, height = image.size
                x_ratio = (1600.0 * 0.7) / float(width)
                y_ratio = (900.0 * 0.7) / float(height)
                ratio = min(x_ratio, y_ratio)
                resized_width = int(ratio * width)

                f.write("\n---\n")
                f.write('<!-- _class: info -->\n') 
                f.write(f'![width:{resized_width}]({img_path})\n')

        # もし有効な画像がない場合、警告を表示
        if not valid_images:
            print(f"Warning: No valid images found above {min_size_kb} KB")
    
    return output_filename

def main(dir="./xmls", keywords=[], min_size_kb=100):
    print("### dir", dir, "keywords", keywords)
    if not os.path.exists(dir):
        print(f"Directory {dir} does not exist.")
        return

    # 指定されたディレクトリが'xmls'の場合、すべてのサブディレクトリを処理
    if os.path.basename(dir) == 'xmls':
        subdirs = [os.path.join(dir, d) for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]
    else:
        subdirs = [dir]

    all_xml_files = []
    for subdir in subdirs:
        xml_files = glob.glob(f"{subdir}/*.xml")
        all_xml_files.extend(xml_files)

    if not all_xml_files:
        print(f"No XML files found in specified directories.")
        return

    print(all_xml_files)
    for file in all_xml_files:
        dirname, filename = os.path.split(file)
        print(dirname, filename)
        output_filename = make_md(dirname, filename, keywords=keywords, min_size_kb=min_size_kb)
        if output_filename:
            print(f"### result stored in {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', "-d", type=str, help='xml dir', default='./xmls')
    parser.add_argument('--min_size_kb', type=int, default=100, help='minimum size of images to include (in KB)')
    parser.add_argument('positional_args', nargs='?', help='query keywords')
    args = parser.parse_args()

    keywords = args.positional_args
    if type(keywords) == str:
        keywords = [keywords]
    elif keywords is None:
        keywords = []

    print(args, keywords)
    
    main(dir=args.dir, keywords=keywords, min_size_kb=args.min_size_kb)