package io.github.lance0174.bmat;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.URI;
import java.security.MessageDigest;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 更新仅来自本仓 Release，下载后以公开摘要校验。 */
final class UpdatePolicy {
    private static final Pattern ASSET = Pattern.compile("BMT-(\\d+\\.\\d+\\.\\d+(?:-(?:alpha|beta|rc)\\.\\d+)?)-android\\.apk");
    private static final Set<String> HOSTS = Set.of("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com");

    static boolean initialUrl(String address, String name) {
        if (name == null) return false;
        Matcher match = ASSET.matcher(name);
        return match.matches() && ("https://github.com/Lance0174/Better-MAS-Tools/releases/download/v"
                + match.group(1) + "/" + name).equals(address);
    }

    static boolean redirectAllowed(String address) {
        try {
            URI uri = URI.create(address);
            return "https".equals(uri.getScheme()) && HOSTS.contains(uri.getHost())
                    && uri.getRawUserInfo() == null && (uri.getPort() == -1 || uri.getPort() == 443);
        } catch (IllegalArgumentException error) { return false; }
    }

    static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder();
        for (byte value : bytes) result.append(String.format(java.util.Locale.ROOT, "%02x", value));
        return result.toString();
    }

    static void copyVerified(InputStream input, File file, long expectedSize, String digest) throws Exception {
        if (expectedSize <= 0 || expectedSize > 512L * 1024 * 1024 || digest == null || !digest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("更新参数无效");
        }
        boolean complete = false;
        try (FileOutputStream output = new FileOutputStream(file)) {
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[65536];
            long size = 0;
            long started = System.nanoTime();
            int count;
            while ((count = input.read(buffer)) != -1) {
                if (Thread.currentThread().isInterrupted() || System.nanoTime() - started > 600_000_000_000L) throw new IllegalArgumentException("更新下载已取消或超时");
                size += count;
                if (size > expectedSize) throw new IllegalArgumentException("更新包大小不符");
                hash.update(buffer, 0, count);
                output.write(buffer, 0, count);
            }
            if (size != expectedSize || !hex(hash.digest()).equals(digest)) throw new IllegalArgumentException("更新包完整性校验失败");
            output.getFD().sync();
            complete = true;
        } finally { if (!complete) file.delete(); }
    }
}
