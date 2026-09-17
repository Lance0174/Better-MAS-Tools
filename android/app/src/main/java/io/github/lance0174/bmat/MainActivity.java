package io.github.lance0174.bmat;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.WindowInsets;
import android.view.Gravity;
import android.webkit.ConsoleMessage;
import android.webkit.WebResourceError;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebMessage;
import android.webkit.WebMessagePort;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONObject;

/** 本地主页面通过定向 MessagePort 使用原生能力；没有通用 JS 注入接口。 */
public final class MainActivity extends Activity {
    private static final int PICK_FILE = 10;
    private static final int SAVE_FILE = 11;
    private final ExecutorService networkPool = Executors.newFixedThreadPool(4);
    private final ExecutorService storagePool = Executors.newSingleThreadExecutor();
    private final NativeNetwork network = new NativeNetwork();
    private WebView webView;
    private WebMessagePort port;
    private LocalStateStore state;
    private NativeDiagnostics diagnostics;
    private Button diagnosticButton;
    private ValueCallback<Uri[]> fileCallback;
    private String saveId;
    private String saveContent;

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        if (webView != null) {
            webView.evaluateJavascript(
                    "window.dispatchEvent(new CustomEvent('bmat-system-theme-change'))", null);
        }
    }

    @Override
    @SuppressLint("SetJavaScriptEnabled")
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        state = new LocalStateStore(getApplicationContext());
        diagnostics = new NativeDiagnostics(getApplicationContext());
        diagnostics.write("Android startup version=" + BuildConfig.VERSION_NAME + " code=" + BuildConfig.VERSION_CODE
                + " SDK=" + Build.VERSION.SDK_INT + " WebView="
                + (WebView.getCurrentWebViewPackage() == null ? "unavailable" : WebView.getCurrentWebViewPackage().versionName));
        FrameLayout container = new FrameLayout(this);
        container.setBackgroundColor(Color.WHITE);
        webView = new WebView(this);
        container.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        diagnosticButton = new Button(this);
        diagnosticButton.setText("启动诊断");
        diagnosticButton.setOnClickListener(view -> showDiagnostics());
        FrameLayout.LayoutParams diagnosticLayout = new FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        diagnosticLayout.bottomMargin = 16;
        container.addView(diagnosticButton, diagnosticLayout);
        setContentView(container);
        container.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        webView.setBackgroundColor(Color.WHITE);
        webView.getSettings().setJavaScriptEnabled(true);
        // 跟随手机系统深色模式。FORCE_DARK_AUTO 让 WebView 按系统 UI 模式上报
        // prefers-color-scheme（前端 Theme=system 依赖它）；AlgorithmicDarkening 补充
        // 对未适配页面做算法转色。两者同时启用才能让 matchMedia 读到系统深浅。
        if (Build.VERSION.SDK_INT >= 33) {
            webView.getSettings().setForceDark(android.webkit.WebSettings.FORCE_DARK_AUTO);
            webView.getSettings().setAlgorithmicDarkeningAllowed(true);
        } else {
            webView.getSettings().setForceDark(android.webkit.WebSettings.FORCE_DARK_AUTO);
        }
        // 仅用于主题等非敏感偏好；账号与抽卡记录由 Keystore 存储。
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setAllowContentAccess(true);
        webView.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.getSettings().setJavaScriptCanOpenWindowsAutomatically(false);
        webView.getSettings().setSupportMultipleWindows(false);
        webView.getSettings().setUserAgentString(webView.getSettings().getUserAgentString() + " BMAT-Android/1");
        webView.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView view, String url, Bitmap favicon) {
                if (port != null) { port.close(); port = null; }
                diagnosticButton.setVisibility(android.view.View.VISIBLE);
                diagnostics.write("Main document loading");
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                String asset = NativePolicy.assetPath(request.getUrl().toString());
                diagnostics.write("Web resource failed code=" + error.getErrorCode() + " asset=" + (asset == null ? "external" : asset));
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                String asset = NativePolicy.assetPath(url);
                if (asset != null) return loadAsset(asset);
                // 极验验证码（含米游币人工验证）资源放行，交由 WebView 安全策略决定；其余外域一律拒绝。
                if (NativePolicy.isCaptchaHost(url)) return null;
                return NativePolicy.isWebResource(url) ? null : missing();
            }

            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (NativePolicy.assetPath(url) != null) return false;
                if (request.isForMainFrame() && request.hasGesture() && NativePolicy.isHttps(url)) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl())); }
                    catch (android.content.ActivityNotFoundException error) { Log.w("BMAT", "没有可打开链接的浏览器"); }
                }
                return true;
            }

            @Override public void onPageFinished(WebView view, String url) {
                if (!"index.html".equals(NativePolicy.assetPath(url))) return;
                // hash 导航可能再次触发完成回调；每份文档只交付一个端口。
                if (port != null) return;
                diagnostics.write("Main page loaded; sending native MessagePort");
                WebMessagePort[] channel = view.createWebMessageChannel();
                port = channel[0];
                port.setWebMessageCallback(new WebMessagePort.WebMessageCallback() {
                    @Override public void onMessage(WebMessagePort incoming, WebMessage message) {
                        receive(message.getData());
                    }
                });
                // Android 将此消息定向到主 frame，验证码 iframe 不获得该端口。
                view.postWebMessage(new WebMessage("bmat-native-ready", new WebMessagePort[]{channel[1]}),
                        Uri.parse(NativePolicy.ORIGIN));
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                diagnostics.write("WebView " + message.messageLevel() + " line=" + message.lineNumber() + " " + message.message());
                return true;
            }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                        .setType("*/*").putExtra(Intent.EXTRA_MIME_TYPES,
                                new String[]{"application/json", "text/plain", "application/octet-stream"});
                try { startActivityForResult(intent, PICK_FILE); }
                catch (android.content.ActivityNotFoundException error) {
                    fileCallback.onReceiveValue(null);
                    fileCallback = null;
                }
                return true;
            }
        });
        webView.loadUrl(NativePolicy.ENTRY);
    }

    private void showDiagnostics() {
        storagePool.execute(() -> {
            String content;
            try { content = diagnostics.read(); }
            catch (Exception error) { content = "诊断文件读取失败：" + error.getClass().getSimpleName(); }
            String report = content.isEmpty() ? "暂无诊断记录" : content;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                TextView text = new TextView(this);
                text.setText(report);
                text.setTextIsSelectable(true);
                text.setPadding(24, 16, 24, 16);
                ScrollView scroll = new ScrollView(this);
                scroll.addView(text);
                new AlertDialog.Builder(this).setTitle("本机启动诊断").setView(scroll)
                        .setNegativeButton("关闭", null)
                        .setPositiveButton("导出日志", (dialog, which) -> {
                            try { beginSave("native-diagnostics", new JSONObject().put("filename", "Better-MAS-Tools-startup.txt").put("content", report)); }
                            catch (Exception error) { diagnostics.write("Diagnostic export failed " + error.getClass().getSimpleName()); }
                        }).show();
            });
        });
    }

    private WebResourceResponse loadAsset(String asset) {
        try {
            String type;
            if (asset.endsWith(".html")) type = "text/html";
            else if (asset.endsWith(".js") || asset.endsWith(".mjs")) type = "text/javascript";
            else if (asset.endsWith(".css")) type = "text/css";
            else if (asset.endsWith(".json")) type = "application/json";
            else if (asset.endsWith(".wasm")) type = "application/wasm";
            else if (asset.endsWith(".svg")) type = "image/svg+xml";
            else if (asset.endsWith(".png")) type = "image/png";
            else if (asset.endsWith(".webp")) type = "image/webp";
            else type = "application/octet-stream";
            InputStream content = getAssets().open(asset);
            WebResourceResponse response = new WebResourceResponse(type, "utf-8", content);
            response.setResponseHeaders(Map.of("X-Content-Type-Options", "nosniff", "Referrer-Policy", "no-referrer",
                    "Content-Security-Policy", NativePolicy.contentPolicy(asset)));
            return response;
        } catch (java.io.IOException error) {
            diagnostics.write("Packaged asset missing: " + asset);
            return missing();
        }
    }

    private static WebResourceResponse missing() {
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", Map.of(),
                new ByteArrayInputStream(new byte[0]));
    }

    private void receive(String serialized) {
        if (serialized == null || serialized.length() > 24_000_000) return;
        try {
            JSONObject request = new JSONObject(serialized);
            String id = request.getString("id");
            String operation = request.getString("operation");
            if (operation.equals("state.read")) diagnostics.write("Native bridge connected; reading encrypted state");
            JSONObject payload = request.optJSONObject("payload");
            if (payload == null) payload = new JSONObject();
            if (operation.equals("file.save")) {
                try { beginSave(id, payload); }
                catch (Exception error) { respond(id, null, "文件保存参数无效"); }
                return;
            }
            JSONObject data = payload;
            int generation = network.generation();
            (operation.equals("http.request") ? networkPool : storagePool).execute(() -> {
                try { respond(id, execute(operation, data, generation), null); }
                catch (Exception error) {
                    // 调用栈交由原生日志统一脱敏；界面仅显示可操作的简要错误。
                    diagnostics.write(operation + "\n" + Log.getStackTraceString(error));
                    respond(id, null, operation.startsWith("state.")
                            ? "手机配置操作未完成，原数据已保留" : "本地操作未完成，请查看日志后重试");
                }
            });
        } catch (Exception error) {
            Log.w("BMAT", "本地消息格式无效");
        }
    }

    private JSONObject execute(String operation, JSONObject payload, int generation) throws Exception {
        switch (operation) {
            case "state.read": {
                String value = state.read();
                return new JSONObject().put("state", value == null ? JSONObject.NULL : value);
            }
            case "state.write":
                state.write(payload.getString("state"));
                return new JSONObject().put("saved", true);
            case "http.request": return network.request(payload, generation);
            case "http.cancel":
                network.cancel(payload.getString("id"));
                return new JSONObject();
            case "http.cancelAll":
                network.close();
                return new JSONObject();
            case "engine.ready":
                diagnostics.write("Python API ready");
                runOnUiThread(() -> diagnosticButton.setVisibility(android.view.View.GONE));
                return new JSONObject();
            case "engine.failed":
                diagnostics.write(payload.optString("message", "Python startup failed"));
                runOnUiThread(() -> diagnosticButton.setVisibility(android.view.View.VISIBLE));
                return new JSONObject();
            case "log.write": {
                diagnostics.write(payload.getString("message"));
                return new JSONObject();
            }
            case "log.read": {
                return new JSONObject().put("content", diagnostics.read());
            }
            default: throw new IllegalArgumentException("Unsupported local operation");
        }
    }

    private void respond(String id, JSONObject result, String error) {
        runOnUiThread(() -> {
            if (id.equals("native-diagnostics")) {
                Toast.makeText(this, error == null ? "日志已保存" : error, Toast.LENGTH_LONG).show();
                return;
            }
            if (port == null || isFinishing() || isDestroyed()) return;
            try {
                JSONObject response = new JSONObject().put("id", id);
                if (error != null) response.put("error", error);
                else response.put("result", result == null ? new JSONObject() : result);
                port.postMessage(new WebMessage(response.toString()));
            } catch (Exception closed) { Log.i("BMAT", "页面已关闭，本次操作结果保留在本地"); }
        });
    }

    private void beginSave(String id, JSONObject data) throws Exception {
        if (saveId != null) {
            respond(id, null, "请先完成当前文件保存");
            return;
        }
        String name = NativePolicy.fileName(data.getString("filename"));
        saveContent = data.getString("content");
        if (saveContent.length() > 16_000_000) {
            saveContent = null;
            respond(id, null, "导出文件过大，请按游戏或角色分别导出");
            return;
        }
        saveId = id;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType(name.toLowerCase(Locale.ROOT).endsWith(".txt") ? "text/plain" : "application/json")
                .putExtra(Intent.EXTRA_TITLE, name);
        try { startActivityForResult(intent, SAVE_FILE); }
        catch (android.content.ActivityNotFoundException error) {
            saveId = null;
            saveContent = null;
            respond(id, null, "系统文件保存器不可用");
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == PICK_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(result == RESULT_OK && data != null && data.getData() != null
                    ? new Uri[]{data.getData()} : null);
            fileCallback = null;
        } else if (request == SAVE_FILE && saveId != null) {
            String id = saveId;
            String content = saveContent;
            saveId = null;
            saveContent = null;
            if (result != RESULT_OK || data == null || data.getData() == null) {
                respond(id, null, "已取消保存");
                return;
            }
            Uri uri = data.getData();
            storagePool.execute(() -> {
                try (OutputStream output = getContentResolver().openOutputStream(uri, "wt")) {
                    if (output == null) throw new java.io.IOException();
                    output.write(content.getBytes(StandardCharsets.UTF_8));
                    output.flush();
                    respond(id, new JSONObject().put("saved", true), null);
                } catch (Exception error) { respond(id, null, "文件保存失败，请重试"); }
            });
        }
    }

    @Override public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        if (port != null) { port.close(); port = null; }
        network.close();
        networkPool.shutdownNow();
        storagePool.shutdown();
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
