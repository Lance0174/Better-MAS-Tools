plugins {
    id("com.android.application")
}

android {
    namespace = "io.github.lance0174.bmat"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.lance0174.bmat"
        minSdk = 29
        targetSdk = 35
        versionCode = 2
        versionName = "0.1.4"
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
