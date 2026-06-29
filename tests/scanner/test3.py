# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : test3.py
# @Time     : 2026/4/15 14:54
# @Desc     : 
from io import BytesIO
import twain
from PIL import Image
import PIL


def silent_scan_and_save(output:str):

    sm = twain.SourceManager(0)
    src = sm.open_source()

    if src is None:
        print("未找到扫描仪")
        return False

    src.set_capability("ICAP_XRESOLUTION", twain.TWTY_FIX32,float(300))
    src.set_capability("ICAP_YRESOLUTION", twain.TWTY_FIX32, float(300))

    src.set_capability("ICAP_PIXELTYPE", twain.TWTY_FIX32, 2)

    src.request_acquire(show_ui=False, modal_ui=False)

    result = src.xfer_image_natively()

    if result is None:
        print("扫描失败")
        src.close()
        sm.close()
        return False

    handle, _ = result

    bmp_bytes = twain.dib_to_bm_file(handle)
    img = Image.open(BytesIO(bmp_bytes), formats=["bmp"])
    img.save(output, "jpg")

    src.close()
    sm.close()
    return True


if __name__ == "__main__":
    output = r"D:/scan_files"
    silent_scan_and_save(output)