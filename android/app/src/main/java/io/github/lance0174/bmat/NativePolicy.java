package io.github.lance0174.bmat;

import java.net.URI;
import java.util.Locale;

/** 只向应用打包的主页面提供本地能力。 */
final class NativePolicy {
    static final String ORIGIN = "https://appassets.androidplatform.net";
    static final String ENTRY = ORIGIN + "/index.html";

    private NativePolicy() {}

    static String assetPath(String value) {
        try {
            URI uri = URI.create(value);
            if (!"https".equals(uri.getScheme())
                    || !"appassets.androidplatform.net".equals(uri.getHost())
                    || uri.getPort() != -1 || uri.getRawUserInfo() != null) return null;
            String path = uri.getPath();
            if (path == null || path.indexOf('\\') >= 0 || path.indexOf('\0') >= 0) return null;
            for (String part : path.split("/")) {
                if (part.equals("..") || part.equals(".")) return null;
            }
            return path.isEmpty() || path.equals("/") ? "index.html" : path.substring(1);
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    static boolean isHttps(String value) {
        try {
            URI uri = URI.create(value);
            return "https".equals(uri.getScheme()) && uri.getHost() != null
                    && uri.getRawUserInfo() == null;
        } catch (IllegalArgumentException error) {
            return false;
        }
    }

    static boolean isWebResource(String value) {
        if (!isHttps(value)) return false;
        String host = URI.create(value).getHost().toLowerCase(Locale.ROOT);
        return host.equals("doc.auto-mas.top") || host.equals("geetest.com")
                || host.endsWith(".geetest.com") || host.equals("geevisit.com")
                || host.endsWith(".geevisit.com") || host.equals("geetest.net")
                || host.endsWith(".geetest.net") || host.equals("gsensebot.com")
                || host.endsWith(".gsensebot.com");
    }

    /** 放行极验官方域（含 http 明文，由 MIXED_CONTENT_NEVER_ALLOW 强制安全策略）；其余外域一律拒绝。 */
    static boolean isCaptchaHost(String value) {
        try {
            URI uri = URI.create(value);
            if (uri.getHost() == null || uri.getRawUserInfo() != null) return false;
            String scheme = uri.getScheme();
            if (scheme == null || !(scheme.equals("https") || scheme.equals("http"))) return false;
            String host = uri.getHost().toLowerCase(Locale.ROOT);
            return host.equals("geetest.com") || host.endsWith(".geetest.com")
                    || host.equals("geevisit.com") || host.endsWith(".geevisit.com")
                    || host.equals("geetest.net") || host.endsWith(".geetest.net")
                    || host.equals("gsensebot.com") || host.endsWith(".gsensebot.com")
                    || host.equals("static.geetest.com");
        } catch (IllegalArgumentException error) {
            return false;
        }
    }

    static String contentPolicy(String asset) {
        if (asset.equals("captcha.html")) {
            // 极验 v3 用 javascript: URL 触发回调，必须放行 'unsafe-inline'；验证码沙箱 iframe 已隔离，风险可控。
            // 极验在 WebView 内可能派生 http 明文请求（与桌面端修复一致）；MIXED_CONTENT_NEVER_ALLOW 仍由 WebView 强制，这里只放开 CSP 域名。
            String hosts = "https://*.geetest.com https://*.geevisit.com https://*.geetest.net https://*.gsensebot.com "
                    + "http://*.geetest.com http://*.geevisit.com http://*.geetest.net http://*.gsensebot.com";
            return "default-src 'none'; script-src 'self' 'unsafe-eval' 'unsafe-inline' " + hosts
                    + "; style-src 'self' 'unsafe-inline' " + hosts + "; img-src data: blob: " + hosts
                    + "; connect-src " + hosts + "; frame-src " + hosts
                    + "; base-uri 'none'; form-action 'none'; frame-ancestors 'self'";
        }
        if (asset.equals("runtime/engine-worker.js")) {
            return "default-src 'none'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; connect-src 'self'";
        }
        return "default-src 'self'; script-src 'self'; worker-src 'self'; style-src 'self' 'unsafe-inline'; "
                + "img-src 'self' data: blob: https://doc.auto-mas.top; font-src 'self' data:; "
                + "connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'";
    }

    static String fileName(String value) {
        String clean = value.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", "_").trim();
        String suffix = clean.toLowerCase(Locale.ROOT).endsWith(".txt") ? ".txt" : ".json";
        int dot = clean.lastIndexOf('.');
        String stem = dot > 0 ? clean.substring(0, dot) : clean;
        if (stem.isBlank() || stem.equals("..")) stem = "Better-MAS-Tools";
        return stem.substring(0, Math.min(stem.length(), 100)) + suffix;
    }
}
