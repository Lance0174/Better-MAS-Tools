package io.github.lance0174.bmat;

import static org.junit.Assert.*;
import org.junit.Test;

public class NativePolicyTest {
    @Test public void bundledAssetsCannotTraverseOrChangeAuthority() {
        assertEquals("index.html", NativePolicy.assetPath(NativePolicy.ORIGIN));
        assertEquals("index.html", NativePolicy.assetPath(NativePolicy.ORIGIN + "/"));
        assertEquals("runtime/pyodide.js", NativePolicy.assetPath(NativePolicy.ORIGIN + "/runtime/pyodide.js"));
        assertNull(NativePolicy.assetPath(NativePolicy.ORIGIN + "/%2e%2e/private"));
        assertNull(NativePolicy.assetPath(NativePolicy.ORIGIN + "/a/%5c..%5cprivate"));
        assertNull(NativePolicy.assetPath("https://user@appassets.androidplatform.net/index.html"));
        assertNull(NativePolicy.assetPath(NativePolicy.ORIGIN + ":444/index.html"));
        assertNull(NativePolicy.assetPath("file:///data/data/other-app/private"));
    }

    @Test public void captchaResourcesUseExactDomainBoundaries() {
        assertTrue(NativePolicy.isWebResource("https://static.geetest.com/v4/gt4.js"));
        assertFalse(NativePolicy.isWebResource("https://static.geetest.com.evil.test/gt4.js"));
        assertFalse(NativePolicy.isWebResource("http://static.geetest.com/gt4.js"));
        assertFalse(NativePolicy.isWebResource("https://evilgeetest.com/gt4.js"));
    }

    @Test public void wikiImagesUseExactAllowedOrigins() {
        assertTrue(NativePolicy.isWebResource("https://data.akedata.wiki/icon.png"));
        assertTrue(NativePolicy.isWebResource("https://resource.starrailassistant.top/banner.png"));
        assertFalse(NativePolicy.isWebResource("https://data.akedata.wiki.evil.test/icon.png"));
    }

    @Test public void exportedNamesExcludePathsAndControlCharacters() {
        String name = NativePolicy.fileName("../account\nrecords.json");
        assertFalse(name.contains("/"));
        assertFalse(name.contains("\n"));
        assertTrue(name.endsWith(".json"));
        assertEquals("Better-MAS-Tools.json", NativePolicy.fileName(""));
    }

    @Test public void nativeRequestsUseOnlyWhitelistedPlatformHosts() {
        assertEquals(
                "as.hypergryph.com",
                NativePolicy.requestHost("https://as.hypergryph.com/user/oauth2/v2/grant"));
        assertEquals(
                "api.kurobbs.com",
                NativePolicy.requestHost("https://api.kurobbs.com/user/mineV2"));
        assertEquals(
                "api-takumi-record.mihoyo.com",
                NativePolicy.requestHost("https://api-takumi-record.mihoyo.com/event/luna/info"));
        // 极验按运行时下发的子域请求，按整域放行。
        assertEquals(
                "gcaptcha4.geetest.com",
                NativePolicy.requestHost("https://gcaptcha4.geetest.com/verify"));
        // 大小写不改变归属，返回值统一为小写主机名。
        assertEquals(
                "zonai.skland.com",
                NativePolicy.requestHost("https://Zonai.SKLAND.com/web/v1/auth/refresh"));
        // 显式默认端口与结尾点等价于同一主机。
        assertEquals(
                "api.kurobbs.com",
                NativePolicy.requestHost("https://api.kurobbs.com:443/user/mineV2"));
        assertEquals(
                "data.akedata.wiki",
                NativePolicy.requestHost("https://data.akedata.wiki./manifest.json"));
    }

    @Test public void nativeRequestsRejectInternalAndDisguisedTargets() {
        assertNull(NativePolicy.requestHost("https://127.0.0.1/api"));
        assertNull(NativePolicy.requestHost("https://10.0.0.5/internal"));
        assertNull(NativePolicy.requestHost("https://172.16.9.9/internal"));
        assertNull(NativePolicy.requestHost("https://192.168.1.1/router"));
        assertNull(NativePolicy.requestHost("https://169.254.169.254/latest/meta-data"));
        assertNull(NativePolicy.requestHost("https://0.0.0.0/api"));
        assertNull(NativePolicy.requestHost("https://[::1]/admin"));
        assertNull(NativePolicy.requestHost("https://[fd00::1]/admin"));
        assertNull(NativePolicy.requestHost("https://router.local/api"));
        assertNull(NativePolicy.requestHost("https://localhost/api"));
        // userinfo 混淆：authority 里的 host 是 internal，必须整条拒绝。
        assertNull(NativePolicy.requestHost("https://evil.com@internal/api"));
        // 白名单外的主机、仅仅"看起来像"的子域、明文 http、非默认端口都不放行。
        assertNull(NativePolicy.requestHost("https://example.com/api"));
        assertNull(NativePolicy.requestHost("https://as.hypergryph.com.evil.test/grant"));
        assertNull(NativePolicy.requestHost("http://as.hypergryph.com/user/oauth2/v2/grant"));
        assertNull(NativePolicy.requestHost("https://as.hypergryph.com:8443/user/oauth2/v2/grant"));
    }

    @Test public void nativeResponseHeadersExposeOnlyPlatformKeys() {
        assertTrue(NativePolicy.isResponseHeader("content-type"));
        assertTrue(NativePolicy.isResponseHeader("Content-Length"));
        assertTrue(NativePolicy.isResponseHeader("Date"));
        assertTrue(NativePolicy.isResponseHeader("set-cookie"));
        assertTrue(NativePolicy.isResponseHeader("x-rpc-signgame"));
        assertFalse(NativePolicy.isResponseHeader("server"));
        assertFalse(NativePolicy.isResponseHeader("x-internal-token"));
        assertFalse(NativePolicy.isResponseHeader(null));
    }

    @Test public void cloudHostsAreNotAvailableOnAndroid() {
        assertNull(NativePolicy.requestHost("https://community.example.workers.dev/api/session"));
        assertNull(NativePolicy.requestHost("https://Community.Example.Workers.dev/api/cloud/sync"));
        assertNull(NativePolicy.requestHost("https://10.0.0.5/internal"));
        assertNull(NativePolicy.requestHost("https://[::1]/admin"));
        assertNull(NativePolicy.requestHost("https://router.local/api"));
        assertNull(NativePolicy.requestHost("https://evil.com@cloud.example.com/api"));
        // 软件更新仅查询本仓 Release；不能把 GitHub API 当成任意请求代理。
        assertEquals(
                "api.github.com", NativePolicy.requestHost("https://api.github.com/repos/Lance0174/Better-MAS-Tools/releases?per_page=30"));
        assertNull(NativePolicy.requestHost("https://api.github.com/repos/other/project/releases"));
    }
}
