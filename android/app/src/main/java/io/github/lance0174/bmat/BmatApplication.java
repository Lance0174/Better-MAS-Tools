package io.github.lance0174.bmat;

import android.app.Application;
import android.webkit.WebView;

/** 预热 WebView：提前初始化 Chromium 加载器与数据目录，缩短冷启动首帧等待。 */
public class BmatApplication extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        try {
            new WebView(getApplicationContext()).destroy();
        } catch (Throwable ignored) {
            // 预热失败不影响正常启动路径。
        }
    }
}
