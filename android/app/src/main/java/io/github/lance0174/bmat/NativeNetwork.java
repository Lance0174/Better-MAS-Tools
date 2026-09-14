package io.github.lance0174.bmat;

import android.os.SystemClock;
import android.util.Base64;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONArray;
import org.json.JSONObject;

/** 平台协议仍在 Python；这里只执行带取消和总时限的 HTTPS 请求。 */
final class NativeNetwork {
    private final ConcurrentHashMap<String, HttpURLConnection> active = new ConcurrentHashMap<>();
    private final Set<String> cancelled = ConcurrentHashMap.newKeySet();
    private final AtomicInteger generation = new AtomicInteger();
    private static final Set<String> METHODS = Set.of("GET", "POST", "PUT", "DELETE", "HEAD");

    int generation() { return generation.get(); }

    JSONObject request(JSONObject data, int expectedGeneration) throws Exception {
        String id = data.getString("id");
        String url = data.getString("url");
        String method = data.getString("method");
        if (!NativePolicy.isHttps(url) || !METHODS.contains(method)) {
            throw new IllegalArgumentException("Unsupported platform request");
        }
        int timeout = Math.max(1000, Math.min(data.getInt("timeoutMs"), 60_000));
        long deadline = SystemClock.elapsedRealtime() + timeout;
        HttpURLConnection connection = (HttpURLConnection) URI.create(url).toURL().openConnection();
        active.put(id, connection);
        try {
            if (generation.get() != expectedGeneration || cancelled.remove(id)) {
                throw new java.io.IOException("Cancelled");
            }
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(Math.min(timeout, 10_000));
            connection.setReadTimeout(timeout);
            connection.setRequestMethod(method);
            JSONArray headers = data.getJSONArray("headers");
            for (int index = 0; index < headers.length(); index++) {
                JSONArray pair = headers.getJSONArray(index);
                String name = pair.getString(0);
                if (!name.equalsIgnoreCase("content-length") && !name.equalsIgnoreCase("host")
                        && !name.equalsIgnoreCase("connection")) {
                    connection.addRequestProperty(name, pair.getString(1));
                }
            }
            byte[] body = Base64.decode(data.optString("body"), Base64.DEFAULT);
            if (body.length > 0) {
                connection.setDoOutput(true);
                connection.setFixedLengthStreamingMode(body.length);
                try (OutputStream stream = connection.getOutputStream()) { stream.write(body); }
            }
            int status = connection.getResponseCode();
            JSONArray responseHeaders = new JSONArray();
            for (Map.Entry<String, List<String>> entry : connection.getHeaderFields().entrySet()) {
                if (entry.getKey() == null) continue;
                for (String value : entry.getValue()) {
                    responseHeaders.put(new JSONArray().put(entry.getKey()).put(value));
                }
            }
            ByteArrayOutputStream content = new ByteArrayOutputStream();
            try (InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream()) {
                if (stream != null) {
                    byte[] chunk = new byte[16_384];
                    int count;
                    while ((count = stream.read(chunk)) != -1) {
                        if (SystemClock.elapsedRealtime() > deadline) throw new SocketTimeoutException();
                        if (content.size() + count > 8_000_000) throw new IllegalArgumentException("Response too large");
                        content.write(chunk, 0, count);
                    }
                }
            }
            return new JSONObject().put("status", status).put("headers", responseHeaders)
                    .put("body", Base64.encodeToString(content.toByteArray(), Base64.NO_WRAP));
        } catch (SocketTimeoutException error) {
            return new JSONObject().put("error", "timeout");
        } catch (java.io.IOException error) {
            return new JSONObject().put("error", "network");
        } finally {
            active.remove(id);
            cancelled.remove(id);
            connection.disconnect();
        }
    }

    void cancel(String id) {
        // 排队中的请求也必须记住取消；条目在该请求结束时移除。
        if (cancelled.size() < 2048) cancelled.add(id);
        HttpURLConnection connection = active.get(id);
        if (connection != null) connection.disconnect();
    }

    void close() {
        generation.incrementAndGet();
        for (HttpURLConnection connection : active.values()) connection.disconnect();
        active.clear();
    }
}
