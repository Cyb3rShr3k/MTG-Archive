"""Application entry point."""
import os
import time
os.environ.setdefault('PYWEBVIEW_GUI', 'qt')
import webview
from backend import Api

if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        title='MTG Card Archive',
        url='web/splash.html',
        js_api=api,
        width=600,
        height=600,
        resizable=True
    )
    def _launch_main(w):
        time.sleep(7)
        w.maximize()
        w.load_url('web/index.html')

    webview.start(func=_launch_main, args=(window,), debug=False, gui='qt')