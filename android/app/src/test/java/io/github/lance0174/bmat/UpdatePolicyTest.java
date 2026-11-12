package io.github.lance0174.bmat;

import static org.junit.Assert.*;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.junit.Test;

public class UpdatePolicyTest {
    @Test public void onlyOfficialVersionedApkCanBeDownloaded() {
        String name = "BMT-0.2.0-beta.5-android.apk";
        String url = "https://github.com/Lance0174/Better-MAS-Tools/releases/download/v0.2.0-beta.5/" + name;
        assertTrue(UpdatePolicy.initialUrl(url, name));
        assertFalse(UpdatePolicy.initialUrl(url + "?redirect=evil", name));
        assertFalse(UpdatePolicy.initialUrl(url.replace("github.com", "evil.test"), name));
        assertFalse(UpdatePolicy.initialUrl(url, "../app.apk"));
        assertFalse(UpdatePolicy.redirectAllowed("https://github.com.evil.test/app.apk"));
        assertFalse(UpdatePolicy.redirectAllowed("https://user@github.com/app.apk"));
        assertFalse(UpdatePolicy.redirectAllowed("http://github.com/app.apk"));
        assertTrue(UpdatePolicy.redirectAllowed("https://release-assets.githubusercontent.com/package"));
    }

    @Test public void checksumAndSizeMustMatchBeforeFileIsKept() throws Exception {
        byte[] payload = "fixture apk bytes".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        String digest = UpdatePolicy.hex(MessageDigest.getInstance("SHA-256").digest(payload));
        File target = File.createTempFile("bmat-update", ".apk");
        try {
            UpdatePolicy.copyVerified(new ByteArrayInputStream(payload), target, payload.length, digest);
            assertArrayEquals(payload, Files.readAllBytes(target.toPath()));
            try {
                UpdatePolicy.copyVerified(new ByteArrayInputStream(payload), target, payload.length - 1, digest);
                fail("Oversized download accepted");
            } catch (IllegalArgumentException expected) { assertFalse(target.exists()); }
            try {
                UpdatePolicy.copyVerified(new ByteArrayInputStream(payload), target, payload.length, "a".repeat(64));
                fail("Corrupted download accepted");
            } catch (IllegalArgumentException expected) { assertFalse(target.exists()); }
        } finally { target.delete(); }
    }
}
