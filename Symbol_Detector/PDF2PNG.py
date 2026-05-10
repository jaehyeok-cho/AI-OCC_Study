import fitz

def convert_pdf_to_ultra_high_res(pdf_path):
    doc = fitz.open(pdf_path)
    generated_files = []

    for i in range(len(doc)):
        page = doc[i]
        dpi = 400
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)

        output_filename = os.path.abspath(f"draw{i}.png")
        pix.save(output_filename)
        print(f"최고 화질 저장 완료: {output_filename}")
        generated_files.append(output_filename)

    doc.close()
    return generated_files