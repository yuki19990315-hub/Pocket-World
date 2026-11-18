package com.sanny.pocketworld;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Local-only protocol for the SANNY ESP32. No cloud account or server. */
public final class SannyApi {
    public static final String BASE = "http://192.168.4.1";
    public static final int MAX_FILE = 128 * 1024;

    private SannyApi() { }

    public interface Progress {
        void onProgress(int bytesSent, int totalBytes);
    }

    public static String uploadName(String filename) {
        if (filename == null) return null;
        if (filename.equals("index.html") || filename.equals("world_model.py")) return filename;
        if (filename.length() > 60 || filename.startsWith(".") || filename.contains("..")) return null;
        if (!filename.matches("[A-Za-z0-9_.-]+")) return null;
        String lower = filename.toLowerCase(java.util.Locale.ROOT);
        if (lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".json") || lower.endsWith(".dat")) {
            return "assets/" + filename;
        }
        return null;
    }

    public static byte[] readLimited(InputStream input) throws IOException {
        if (input == null) throw new IOException("ファイルを読み込めません");
        try (InputStream in = input; ByteArrayOutputStream data = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int n;
            while ((n = in.read(buffer)) != -1) {
                if (data.size() + n > MAX_FILE) throw new IOException("ファイルは128KB以下にしてください");
                data.write(buffer, 0, n);
            }
            if (data.size() == 0) throw new IOException("空のファイルは送信できません");
            return data.toByteArray();
        }
    }

    private static HttpURLConnection request(String path, String method, String secret) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(BASE + path).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(6000);
        connection.setReadTimeout(14000);
        connection.setUseCaches(false);
        connection.setInstanceFollowRedirects(false);
        if (secret != null) connection.setRequestProperty("X-Admin-Key", secret);
        return connection;
    }

    private static String readResponse(HttpURLConnection connection) throws IOException {
        int code = connection.getResponseCode();
        InputStream stream = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String result;
        if (stream == null) result = "";
        else try (InputStream in = stream; ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
            byte[] bytes = new byte[1024];
            int n;
            while ((n = in.read(bytes)) != -1 && buffer.size() < 8192) buffer.write(bytes, 0, n);
            result = buffer.toString("UTF-8");
        }
        if (code < 200 || code >= 300) throw new IOException("サンニーからエラー " + code + ": " + result);
        return result;
    }

    public static String info() throws IOException {
        HttpURLConnection connection = request("/api/info", "GET", null);
        try { return readResponse(connection); }
        finally { connection.disconnect(); }
    }

    public static String upload(String filename, byte[] data, String secret, Progress progress) throws IOException {
        String target = uploadName(filename);
        if (target == null) throw new IOException("このファイル形式は更新に対応していません");
        if (data == null || data.length == 0 || data.length > MAX_FILE) throw new IOException("ファイルは1〜128KBにしてください");
        if (secret == null || secret.trim().isEmpty()) throw new IOException("更新キーを入力してください");
        HttpURLConnection connection = request("/api/upload", "POST", secret);
        try {
            connection.setRequestProperty("Content-Type", "application/octet-stream");
            connection.setRequestProperty("X-File-Name", target);
            connection.setFixedLengthStreamingMode(data.length);
            connection.setDoOutput(true);
            try (OutputStream out = connection.getOutputStream()) {
                int offset = 0;
                while (offset < data.length) {
                    int count = Math.min(4096, data.length - offset);
                    out.write(data, offset, count);
                    offset += count;
                    if (progress != null) progress.onProgress(offset, data.length);
                }
            }
            return readResponse(connection);
        } finally { connection.disconnect(); }
    }

    public static String restart(String secret) throws IOException {
        if (secret == null || secret.trim().isEmpty()) throw new IOException("更新キーを入力してください");
        HttpURLConnection connection = request("/api/restart", "POST", secret);
        try {
            connection.setDoOutput(true);
            connection.setFixedLengthStreamingMode(0);
            try (OutputStream out = connection.getOutputStream()) { out.flush(); }
            return readResponse(connection);
        } finally { connection.disconnect(); }
    }
}
