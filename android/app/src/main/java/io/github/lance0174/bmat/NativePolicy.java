package io.github.lance0174.bmat;

import java.net.URI;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** 只向应用打包的主页面提供本地能力。 */
final class NativePolicy {
    static final String ORIGIN = "https://appassets.androidplatform.net";
    static final String ENTRY = ORIGIN + "/index.html";

    /** 单次请求声明的额外主机上限；云端/转发层只会有一个后端，8 项已远超实际需要。 */
    static final int MAX_ALLOW_HOSTS = 8;

    /**
     * 原生代发请求的上游主机白名单：逐条来自 app/tools/*.py 与 app/services/*.py 里真实发出的
     * HTTPS 请求（注释里的行号是逐个 grep 核实的来源）。WebView 侧一旦出现 XSS，也不能再借原生
     * 层代发任意 https 主机，内网探测/SSRF 通道与绕过 CSP connect-src 的通道一起关掉。
     */
    private static final Set<String> PLATFORM_HOSTS = Set.of(
            // 森空岛/鹰角：通行证授权、角色绑定、签到与扫码（app/tools/skland.py:79-88）
            "zonai.skland.com",
            "as.hypergryph.com",
            "ak.hypergryph.com",
            "binding-api-account-prod.hypergryph.com",
            // 终末地 webview 寻访记录（app/tools/gacha.py:373-380）
            "ef-webview.hypergryph.com",
            "ef-webview.gryphline.com",
            // 米游社/米哈游：签到、便笺与凭据派生（app/tools/miyoushe.py:61-70）
            "api-takumi.mihoyo.com",
            "act-nap-api.mihoyo.com",
            // 米游社活动记录接口与设备登录（community_activity_transport.py:72、
            // community_activity_provider.py:84-89）
            "api-takumi-record.mihoyo.com",
            "bbs-api.mihoyo.com",
            "public-data-api.mihoyo.com",
            // 米游社扫码登录与 Token 派生（app/tools/miyoushe_qr.py:66-101）
            "passport-api.mihoyo.com",
            "passport-api.miyoushe.com",
            "hk4e-sdk.mihoyo.com",
            // 米游社帖子任务与云原神凭据（miyoushe_bbs.py:16、cloud_genshin.py:43-45）
            "bbs-api.miyoushe.com",
            "api-cloudgame.mihoyo.com",
            // 抽卡记录按 game_biz 拼出的国服/国际服固定主机（gacha.py:21-28,114-120）
            "public-operation-hk4e.mihoyo.com",
            "public-operation-hkrpg.mihoyo.com",
            "public-operation-nap.mihoyo.com",
            "public-operation-hk4e-sg.hoyoverse.com",
            "public-operation-hkrpg-sg.hoyoverse.com",
            "public-operation-nap-sg.hoyoverse.com",
            // 库街区：签到、用户信息、短信登录（app/tools/kuro.py:327-450）
            "api.kurobbs.com",
            // 塔吉多与老虎用户中心（app/tools/taygedo.py:59-69,106）
            "bbs-api.tajiduo.com",
            "user.laohu.com",
            // 鸣潮抽卡记录（app/tools/gacha.py:216-220）
            "gmserver-api.aki-game2.com",
            "gmserver-api.aki-game2.net",
            // 终末地资料库与活动日历（akedata_client.py:62-69、sra_activity.py:53）
            "data.akedata.wiki",
            "www.akedata.wiki",
            "starrailassistant.top",
            // 明日方舟活动表（game_calendar_arknights.py:48-51）
            "raw.githubusercontent.com",
            // 第三方校时与打码（community_sign_provider.py:124、yunma.py:11）
            "worldtimeapi.org",
            "api.jfbym.com");

    /**
     * 整域放行的上游：极验会按运行时下发的子域请求（app/tools/_geetest/geetest.py:74,152、
     * track_detact/slide.py:104），逐个枚举会在验证码改版时静默失败。
     */
    private static final Set<String> PLATFORM_SUFFIXES = Set.of(
            "geetest.com", "geevisit.com", "geetest.net", "gsensebot.com");

    /**
     * 回传 JS 的响应头白名单，只留 Python 侧真正读取的键：content-type 供 network.py:39 判断
     * JSON，Date/Age 供 skland.py:123-139 校时，set-cookie 供 miyoushe_qr.py:1103，
     * location 供 follow_redirects 的跳转；其余响应头一律不回传。
     */
    private static final Set<String> RESPONSE_HEADERS = Set.of(
            "content-type", "content-length", "date", "age", "location", "set-cookie", "retcode");

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

    /**
     * 校验原生代发请求的目标；通过时返回小写主机名，拒绝时返回 null。
     * 拒绝原因（非白名单、内网地址、userinfo 混淆）在调用方统一成一个文案，不把内部细节回传 JS。
     */
    static String requestHost(String value) {
        return requestHost(value, List.of());
    }

    /**
     * 同上，额外接受本次请求显式声明的主机（安卓端用户配置的云端后端/转发层）。
     * allowHosts 只对该次请求生效、不写入任何静态状态，且每一项仍要通过语法与内网拒绝规则；
     * 它是白名单之外的唯一增量，无法借此指向任意公网主机——只有 Python 侧确认目标就是云端
     * 主机时才会声明，原生层只做"这一条是否等于本次请求主机"的比对。
     */
    static String requestHost(String value, List<String> allowHosts) {
        try {
            URI uri = URI.create(value);
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null) return null;
            // `https://evil.com@internal/` 会把 userinfo 解析进 authority，整条拒绝而不是只信
            // host 字段；否则 JS 只要拼一个 @ 就能把请求指到任意主机。
            if (uri.getRawUserInfo() != null) return null;
            // 只接受默认端口：白名单主机上的其他端口同样可能是内网转发或探测入口。
            if (uri.getPort() != -1 && uri.getPort() != 443) return null;
            String host = uri.getHost().toLowerCase(Locale.ROOT);
            // 结尾点等价于同一主机（"as.hypergryph.com."），归一化后再匹配避免绕过。
            if (host.endsWith(".")) host = host.substring(0, host.length() - 1);
            if (host.isEmpty() || host.endsWith(".") || host.indexOf('%') >= 0) return null;
            if (isInternalAddress(host)) return null;
            if (isPlatformHost(host) || declaredHost(host, allowHosts)) return host;
            return null;
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    /** 本次请求声明的允许主机是否包含该主机；条数超限或存在非法条目都按整体拒绝处理。 */
    private static boolean declaredHost(String host, List<String> allowHosts) {
        if (allowHosts == null || allowHosts.isEmpty()) return false;
        if (allowHosts.size() > MAX_ALLOW_HOSTS) return false;
        boolean matched = false;
        for (String entry : allowHosts) {
            String allowed = allowedHost(entry);
            // 有一条不合法就整条拒绝，不做"忽略坏项继续放行"的容错，避免宽容度被套利。
            if (allowed == null) return false;
            matched |= allowed.equals(host);
        }
        return matched;
    }

    /**
     * 校验并归一化一条声明主机。云端后端是公网 https 主机，本来就不在 PLATFORM_HOSTS 里，
     * 所以这里只复用 userinfo/私网/环回/链路本地/`.local` 等拒绝规则加 DNS 语法，不复用白名单。
     */
    private static String allowedHost(String value) {
        if (value == null) return null;
        String host = value.trim().toLowerCase(Locale.ROOT);
        if (host.endsWith(".")) host = host.substring(0, host.length() - 1);
        if (host.isEmpty() || host.length() > 253 || host.endsWith(".")) return null;
        if (host.indexOf("..") >= 0 || host.startsWith("-") || host.startsWith(".")) return null;
        for (int index = 0; index < host.length(); index++) {
            char letter = host.charAt(index);
            // 只接受 DNS 名：@ % : / 等字符代表 userinfo、转义或端口歧义，一律拒绝。
            boolean plain = (letter >= 'a' && letter <= 'z') || (letter >= '0' && letter <= '9')
                    || letter == '-' || letter == '.';
            if (!plain) return null;
        }
        if (host.endsWith("-")) return null;
        return isInternalAddress(host) ? null : host;
    }

    static boolean isPlatformHost(String host) {
        if (PLATFORM_HOSTS.contains(host)) return true;
        for (String suffix : PLATFORM_SUFFIXES) {
            if (host.equals(suffix) || host.endsWith("." + suffix)) return true;
        }
        return false;
    }

    /**
     * 私网/环回/链路本地与本地名字面量：即使白名单将来误登记，也要先被这条挡住。
     * 覆盖 10/8、172.16/12、192.168/16、127/8、169.254/16、0.0.0.0、::1、fc00::/7、fe80::/10。
     */
    private static boolean isInternalAddress(String host) {
        if (host.equals("localhost") || host.endsWith(".localhost")) return true;
        // mDNS（.local）与内网后缀解析到哪台机器由局域网决定，不能交给系统解析器。
        if (host.endsWith(".local") || host.endsWith(".internal")) return true;
        // 整数形式的 IPv4（2130706433 等价于 127.0.0.1）同样按字面量处理。
        boolean digits = !host.isEmpty();
        for (int index = 0; index < host.length() && digits; index++) {
            char value = host.charAt(index);
            digits = value >= '0' && value <= '9';
        }
        return digits || isPrivateIpv4(host) || isPrivateIpv6(host);
    }

    private static boolean isPrivateIpv4(String host) {
        String[] parts = host.split("\\.", -1);
        if (parts.length != 4) return false;
        int[] octets = new int[4];
        for (int index = 0; index < 4; index++) {
            String part = parts[index];
            if (part.isEmpty() || part.length() > 3) return false;
            for (int digit = 0; digit < part.length(); digit++) {
                char value = part.charAt(digit);
                if (value < '0' || value > '9') return false;
            }
            octets[index] = Integer.parseInt(part);
            if (octets[index] > 255) return false;
        }
        return octets[0] == 0 || octets[0] == 10 || octets[0] == 127
                || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31)
                || (octets[0] == 192 && octets[1] == 168)
                || (octets[0] == 169 && octets[1] == 254);
    }

    private static boolean isPrivateIpv6(String host) {
        String value = host;
        // URI 把 IPv6 字面量解析成带方括号的形式（[::1]），先剥掉方括号再判断。
        if (value.startsWith("[") && value.endsWith("]")) {
            value = value.substring(1, value.length() - 1);
        }
        if (value.indexOf(':') < 0) return false;
        // ::ffff:10.0.0.1 这类内嵌 IPv4 的映射写法一律拒绝。
        if (value.indexOf('.') > 0) return true;
        if (value.equals("::1") || value.equals("::")) return true;
        // fc00::/7 唯一本地地址（fc/fd 开头）。
        if (value.startsWith("fc") || value.startsWith("fd")) return true;
        // fe80::/10 链路本地。
        return value.startsWith("fe8") || value.startsWith("fe9")
                || value.startsWith("fea") || value.startsWith("feb");
    }

    /** 白名单之外的响应头一律不回传，避免把上游内部标记通过 JS 暴露给页面。 */
    static boolean isResponseHeader(String name) {
        if (name == null) return false;
        String key = name.toLowerCase(Locale.ROOT);
        return RESPONSE_HEADERS.contains(key) || key.startsWith("x-rpc-");
    }

    static boolean isWebResource(String value) {
        if (!isHttps(value)) return false;
        String host = URI.create(value).getHost().toLowerCase(Locale.ROOT);
        return host.equals("doc.auto-mas.top") || host.equals("data.akedata.wiki")
                || host.equals("www.akedata.wiki") || host.equals("resource.starrailassistant.top")
                || host.equals("prod-alicdn-community.kurobbs.com")
                || host.equals("webusstatic.yo-star.com") || host.equals("web.hycdn.cn")
                || host.equals("aka.doubaocdn.com") || host.equals("i0.hdslb.com")
                || host.equals("geetest.com")
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
                + "img-src 'self' data: blob: https://doc.auto-mas.top https://data.akedata.wiki "
                + "https://www.akedata.wiki https://resource.starrailassistant.top "
                + "https://prod-alicdn-community.kurobbs.com https://webusstatic.yo-star.com "
                + "https://web.hycdn.cn https://aka.doubaocdn.com https://i0.hdslb.com; font-src 'self' data:; "
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
