import java.util.Properties
import java.security.KeyStore
import java.security.MessageDigest

plugins {
    id("com.android.application")
}

// 本地读忽略的 keystore.properties，CI 从 Secrets 注入。发布任务绝不回退调试签名。
val keystorePropertiesFile = rootProject.file("keystore.properties")
val keystoreProperties = Properties().apply {
    if (keystorePropertiesFile.isFile) {
        keystorePropertiesFile.inputStream().use { load(it) }
    }
}

fun keystoreValue(key: String): String? = System.getenv(mapOf(
    "storeFile" to "ANDROID_KEYSTORE_PATH", "storePassword" to "ANDROID_KEYSTORE_PASSWORD",
    "keyAlias" to "ANDROID_KEY_ALIAS", "keyPassword" to "ANDROID_KEY_PASSWORD"
)[key])?.takeIf { it.isNotBlank() } ?: keystoreProperties.getProperty(key)?.takeIf { it.isNotBlank() }

val releaseStoreFile = keystoreValue("storeFile")?.let { rootProject.file(it) }
val hasReleaseSigning = releaseStoreFile?.isFile == true &&
    keystoreValue("storePassword") != null &&
    keystoreValue("keyAlias") != null && keystoreValue("keyPassword") != null

val releaseCertificateSha256 = rootProject.file("signing-certificate.sha256").readText().trim()
val verifyReleaseIdentity = tasks.register("verifyReleaseIdentity") {
    doLast {
        check(hasReleaseSigning) { "发布签名缺失：请提供固定密钥与完整配置，禁止使用临时调试签名" }
        val store = KeyStore.getInstance(releaseStoreFile!!, keystoreValue("storePassword")!!.toCharArray())
        val alias = keystoreValue("keyAlias")!!
        check(store.isKeyEntry(alias)) { "发布密钥别名无效" }
        val certificate = store.getCertificate(alias)
        val actual = MessageDigest.getInstance("SHA-256").digest(certificate.encoded)
            .joinToString("") { "%02x".format(it) }
        check(actual == releaseCertificateSha256) { "发布证书与仓库固定指纹不一致，拒绝换签名" }
        logger.lifecycle("Release certificate SHA-256: $actual")
    }
}
tasks.configureEach {
    if (name == "preReleaseBuild") dependsOn(verifyReleaseIdentity)
}

android {
    namespace = "io.github.lance0174.bmat"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.lance0174.bmat"
        minSdk = 29
        targetSdk = 35
        versionCode = 2003
        versionName = "0.2.0-beta.4"
        buildConfigField("String", "RELEASE_CERTIFICATE_SHA256", "\"$releaseCertificateSha256\"")
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = releaseStoreFile!!
                storePassword = keystoreValue("storePassword")
                keyAlias = keystoreValue("keyAlias")
                keyPassword = keystoreValue("keyPassword")
            }
        }
    }

    buildTypes {
        getByName("release") {
            isDebuggable = false
            if (hasReleaseSigning) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    androidResources { noCompress += listOf("wasm", "whl", "zip") }
    lint { abortOnError = true }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
