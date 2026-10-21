package io.github.lance0174.bmat;

import android.content.Context;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/** 资料库缓存只允许写入应用私有目录中的相对 JSON 路径。 */
final class WikiCacheStore {
    private static final int MAX_BYTES = 8_000_000;
    private final File root;

    WikiCacheStore(Context context) {
        root = new File(context.getFilesDir(), "wiki");
    }

    String read(String path) throws IOException {
        File file = resolve(path);
        if (!file.isFile()) return null;
        if (file.length() > MAX_BYTES) throw new IOException("资料库缓存过大");
        try (FileInputStream input = new FileInputStream(file);
                ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            int total = 0;
            while ((count = input.read(buffer)) >= 0) {
                total += count;
                if (total > MAX_BYTES) throw new IOException("资料库缓存过大");
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    void write(String path, String content) throws IOException {
        File file = resolve(path);
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        if (bytes.length > MAX_BYTES) throw new IOException("资料库缓存过大");
        File parent = file.getParentFile();
        if (parent == null || (!parent.exists() && !parent.mkdirs()))
            throw new IOException("资料库缓存目录不可用");
        File temporary = new File(parent, file.getName() + ".tmp");
        boolean replaced = false;
        try {
            try (FileOutputStream output = new FileOutputStream(temporary)) {
                output.write(bytes);
                output.flush();
            }
            if (!temporary.renameTo(file)) throw new IOException("资料库缓存替换失败");
            replaced = true;
        } finally {
            if (!replaced && temporary.exists()) temporary.delete();
        }
    }

    private File resolve(String path) throws IOException {
        if (path == null || !path.startsWith("wiki/") || !path.endsWith(".json")
                || path.length() > 160 || path.indexOf('\\') >= 0 || path.contains(".."))
            throw new IOException("资料库缓存路径无效");
        String relative = path.substring("wiki/".length());
        File file = new File(root, relative);
        String rootPath = root.getCanonicalPath() + File.separator;
        if (!file.getCanonicalPath().startsWith(rootPath))
            throw new IOException("资料库缓存路径无效");
        return file;
    }
}
