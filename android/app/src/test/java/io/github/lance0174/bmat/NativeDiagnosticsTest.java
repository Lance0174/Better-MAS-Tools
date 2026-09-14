package io.github.lance0174.bmat;

import static org.junit.Assert.*;
import org.junit.Test;

public class NativeDiagnosticsTest {
    @Test public void startupDiagnosticsExcludeCredentialsAndUrlQueries() {
        String safe = NativeDiagnostics.sanitize("cookie=fixture-cookie token=fixture-token phone=13800138000 https://example.invalid/api?authkey=fixture-auth");
        assertFalse(safe.contains("fixture-cookie"));
        assertFalse(safe.contains("fixture-token"));
        assertFalse(safe.contains("13800138000"));
        assertFalse(safe.contains("fixture-auth"));
        assertTrue(safe.contains("https://example.invalid/api"));
    }
}
