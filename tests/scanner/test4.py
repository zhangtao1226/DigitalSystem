# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : test4.py
# @Time     : 2026/5/18 9:06
# @Desc     : 
import time
import twain

class TwainScanner:
    def __init__(self):
        self.sm = None
        self.source = None


    def scan_callback(self, event):
        if event == twain.MSG_XFERREADY:
            print("收到信号：图像已就绪， 开始传输·····")
            try:
                handle, count = self.source.xfer_image_natively()
                if handle:
                    print(f"成功获取一页图像， 剩余提示计数：{count}")

                if count == 0:
                    print("检测到最后一页传输完毕, 主动终止后续检测")
                    self.source.cancel_pending_xfer()
                    self.source.stop_scanning()
            except Exception as e:
                print(f"传输图像出错：{e}")
                self.source.stop_scanning()

        elif event == twain.MSG_CLOSEDSREQ:
            print("收到信号：驱动程序请求关闭")
            self.source.stop_scanning()

    def start_scanning(self):
        self.sm = twain.SourceManager(0)
        self.source = self.sm.open_source()
        if not self.source:
            print("未找到扫描仪")
            return

        self.source.set_capability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
        self.source.set_capability(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True)

        try:
            self.source.set_capability(twain.CAP_FEEDERTIMEOUT, twain.TWTY_INT16, 0)
            print(1111)
        except Exception:
            pass

        # print("正在注册回调函数")
        self.source.set_callback(self.scan_callback)

        print("启动扫描仪····")
        self.source.enable_source(show_ui=False)

        print("进入事件循环监听状态······")
        while self.source is not None:
            self.sm.handle_message()
            time.sleep(0.01)


    def stop_scanning(self):
        print("正在释放资源并关闭扫描仪·····")
        if self.source:
            try:
                self.source.disable_source()
            except Exception:
                pass

            self.source = None

        if self.sm:
            self.sm.close()
            self.sm = None

if __name__ == "__main__":
    scanner = TwainScanner()
    scanner.start_scanning()
