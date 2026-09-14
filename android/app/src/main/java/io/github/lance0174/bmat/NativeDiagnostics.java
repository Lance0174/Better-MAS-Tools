package io.github.lance0174.bmat;

import android.content.Context;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** 启动诊断不依赖 WebView、Python 或 HTTP 会话。 */
final class NativeDiagnostics {
    private final File directory;
    NativeDiagnostics(Context context) { directory = context.getFilesDir(); }

    static String sanitize(String value) {
        return value
                .replaceAll("(?i)([\\w-]*(?:token|cookie|password|secret|ticket|authkey|api_?key|authorization|cred|phone|captcha_output|lot_number)[\\w-]*[\\\"']?\\s*[:=]\\s*[\\\"']?)[^\\s,;\\\"'}]+", "$1***")
                .replaceAll("(?i)(https?://)[^/\\s@]+@", "$1***@")
                .replaceAll("(?i)(https?://[^\\s?#]+)[?#][^\\s]*", "$1")
                .replaceAll("\\b1[3-9]\\d{9}\\b", "***")
                .replaceAll("\\b[A-Za-z0-9_-]{32,}\\b", "***");
    }

    synchronized void write(String value) {
        String safe = sanitize(value);
        if (safe.length() > 16_000) safe = safe.substring(0, 16_000);
        String line = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.ROOT).format(new Date()) + " | " + safe;
        Log.i("BMAT", line);
        try {
            File log = new File(directory, "community.log");
            if (log.length() > 2_000_000) {
                Files.move(log.toPath(), new File(directory, "community.previous.log").toPath(), StandardCopyOption.REPLACE_EXISTING);
            }
            try (FileOutputStream output = new FileOutputStream(log, true)) {
                output.write((line + "\n").getBytes(StandardCharsets.UTF_8));
            }
        } catch (Exception error) { Log.w("BMAT", "Cannot write diagnostic file: " + error.getClass().getSimpleName()); }
    }

    synchronized String read() throws Exception {
        StringBuilder result = new StringBuilder();
        for (String name : new String[]{"community.previous.log", "community.log"}) {
            File file = new File(directory, name);
            if (file.exists()) result.append(new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8));
        }
        return result.toString();
    }
}
