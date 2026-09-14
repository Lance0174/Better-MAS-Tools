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

    @Test public void exportedNamesExcludePathsAndControlCharacters() {
        String name = NativePolicy.fileName("../account\nrecords.json");
        assertFalse(name.contains("/"));
        assertFalse(name.contains("\n"));
        assertTrue(name.endsWith(".json"));
        assertEquals("Better-MAS-Tools.json", NativePolicy.fileName(""));
    }
}
