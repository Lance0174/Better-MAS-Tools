package io.github.lance0174.bmat;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.KeyStore;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** 主密钥留在 Android Keystore；保存失败时保留上一份完整配置。 */
final class LocalStateStore {
    private static final String ALIAS = "bmat.local.state.v1";
    private static final byte[] HEADER = "BMAT1".getBytes(StandardCharsets.US_ASCII);
    private final File target;

    LocalStateStore(Context context) {
        target = new File(context.getFilesDir(), "community-state.bin");
    }

    private SecretKey key(boolean create) throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(ALIAS)) return (SecretKey) store.getKey(ALIAS, null);
        if (!create) throw new IllegalStateException("Original key is unavailable");
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }

    synchronized String read() throws Exception {
        if (!target.exists()) return null;
        byte[] stored = Files.readAllBytes(target.toPath());
        if (stored.length < 33 || !Arrays.equals(HEADER, Arrays.copyOf(stored, 5))) {
            throw new IllegalStateException("Invalid stored state");
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(false), new GCMParameterSpec(128, stored, 5, 12));
        cipher.updateAAD(HEADER);
        return new String(cipher.doFinal(stored, 17, stored.length - 17), StandardCharsets.UTF_8);
    }

    synchronized void write(String value) throws Exception {
        byte[] plain = value.getBytes(StandardCharsets.UTF_8);
        if (plain.length > 16_000_000) throw new IllegalArgumentException("State too large");
        // 现有密文存在时不生成替代密钥，避免覆盖无法解密的旧数据。
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key(!target.exists()));
        cipher.updateAAD(HEADER);
        byte[] encrypted = cipher.doFinal(plain);
        File temporary = new File(target.getParentFile(), "community-state.pending");
        try (FileOutputStream stream = new FileOutputStream(temporary)) {
            stream.write(HEADER);
            stream.write(cipher.getIV());
            stream.write(encrypted);
            stream.getFD().sync();
        }
        Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING);
    }
}
