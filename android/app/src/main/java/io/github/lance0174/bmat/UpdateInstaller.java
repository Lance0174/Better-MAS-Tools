package io.github.lance0174.bmat;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.provider.Settings;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

/** 原生安装入口；无任意本机路径，安装前再次检查摘要、包名、版本与证书。 */
final class UpdateInstaller {
    private final Activity activity;
    private String expectedDigest;
    private boolean ready;
    private final AtomicBoolean busy = new AtomicBoolean();
    private volatile HttpURLConnection active;
    private volatile boolean closed;

    UpdateInstaller(Activity activity) { this.activity = activity; }
    private File file() { return new File(activity.getCacheDir(), "bmat-update.apk"); }

    JSONObject download(JSONObject data) throws Exception {
        if (closed) throw new IllegalArgumentException("更新下载已取消");
        if (!busy.compareAndSet(false, true)) throw new IllegalArgumentException("已有更新操作正在进行");
        try { return downloadChecked(data); }
        finally { busy.set(false); }
    }

    private JSONObject downloadChecked(JSONObject data) throws Exception {
        ready = false;
        expectedDigest = null;
        File target = file();
        target.delete();
        String address = data.getString("downloadUrl");
        if (!UpdatePolicy.initialUrl(address, data.getString("assetName"))) throw new IllegalArgumentException("更新包来源无效");
        String digest = data.getString("sha256");
        for (int hop = 0; hop < 6; hop++) {
            if (closed || Thread.currentThread().isInterrupted()) throw new IllegalArgumentException("更新下载已取消");
            if (!UpdatePolicy.redirectAllowed(address)) throw new IllegalArgumentException("更新下载跳转到非官方来源");
            HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
            active = connection;
            try {
                if (closed) throw new IllegalArgumentException("更新下载已取消");
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(25000);
                connection.setReadTimeout(60000);
                connection.setRequestProperty("User-Agent", "Better-MAS-Tools-update");
                int status = connection.getResponseCode();
                if (status == 301 || status == 302 || status == 303 || status == 307 || status == 308) {
                    String next = connection.getHeaderField("Location");
                    if (next == null) throw new IllegalArgumentException("更新下载地址失效");
                    address = new URL(new URL(address), next).toString();
                    continue;
                }
                if (status != 200) throw new IllegalArgumentException("更新包下载失败，请稍后重试");
                try (InputStream input = connection.getInputStream()) {
                    UpdatePolicy.copyVerified(input, target, data.getLong("size"), digest);
                }
                try { verifyPackage(target); }
                catch (Exception error) { target.delete(); throw error; }
                expectedDigest = digest;
                ready = true;
                return new JSONObject().put("ready", true);
            } finally { connection.disconnect(); active = null; }
        }
        throw new IllegalArgumentException("更新下载跳转次数过多");
    }

    private void verifyPackage(File target) throws Exception {
        PackageManager manager = activity.getPackageManager();
        PackageInfo candidate = manager.getPackageArchiveInfo(target.getAbsolutePath(), PackageManager.GET_SIGNING_CERTIFICATES);
        PackageInfo installed = manager.getPackageInfo(activity.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
        if (candidate == null || !activity.getPackageName().equals(candidate.packageName)
                || candidate.getLongVersionCode() <= installed.getLongVersionCode()) throw new IllegalArgumentException("更新包名或版本无效");
        if (candidate.signingInfo == null || installed.signingInfo == null) throw new IllegalArgumentException("无法验证更新签名");
        Signature[] proposed = candidate.signingInfo.getApkContentsSigners();
        Signature[] current = installed.signingInfo.getApkContentsSigners();
        if (proposed.length != 1 || current.length != 1) throw new IllegalArgumentException("更新签名无效");
        String next = UpdatePolicy.hex(MessageDigest.getInstance("SHA-256").digest(proposed[0].toByteArray()));
        String now = UpdatePolicy.hex(MessageDigest.getInstance("SHA-256").digest(current[0].toByteArray()));
        if (!next.equals(BuildConfig.RELEASE_CERTIFICATE_SHA256) || !next.equals(now)) throw new IllegalArgumentException("更新证书与当前应用不一致，无法覆盖安装");
    }

    JSONObject install() throws Exception {
        if (closed) throw new IllegalArgumentException("更新操作已取消");
        if (!busy.compareAndSet(false, true)) throw new IllegalArgumentException("已有更新操作正在进行");
        try { return installChecked(); }
        finally { busy.set(false); }
    }

    private JSONObject installChecked() throws Exception {
        File target = file();
        if (!ready || expectedDigest == null || !target.isFile()) throw new IllegalArgumentException("请先下载并校验更新包");
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new FileInputStream(target)) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = input.read(buffer)) != -1) hash.update(buffer, 0, count);
        }
        if (!UpdatePolicy.hex(hash.digest()).equals(expectedDigest)) {
            ready = false;
            throw new IllegalArgumentException("更新包已变化，请重新下载");
        }
        verifyPackage(target);
        // 大文件摘要及包解析留在后台，只把系统界面启动交回主线程。
        FutureTask<JSONObject> launch = new FutureTask<>(this::launchInstaller);
        activity.runOnUiThread(launch);
        try { return launch.get(15, TimeUnit.SECONDS); }
        finally { launch.cancel(false); }
    }

    private JSONObject launchInstaller() throws Exception {
        if (closed || activity.isFinishing() || activity.isDestroyed()) throw new IllegalArgumentException("更新操作已取消");
        if (!activity.getPackageManager().canRequestPackageInstalls()) {
            activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + activity.getPackageName())));
            return new JSONObject().put("permissionRequired", true);
        }
        Intent install = new Intent(Intent.ACTION_VIEW);
        install.setDataAndType(Uri.parse("content://" + activity.getPackageName() + ".updates/package.apk"), "application/vnd.android.package-archive");
        install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        activity.startActivity(install);
        return new JSONObject().put("installing", true);
    }

    void close() {
        closed = true;
        HttpURLConnection connection = active;
        if (connection != null) connection.disconnect();
    }
}
