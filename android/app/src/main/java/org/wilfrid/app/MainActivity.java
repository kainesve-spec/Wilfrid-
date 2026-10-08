package org.wilfrid.app;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

/**
 * Wilfrid — coquille d'interface, zéro moteur décisionnel.
 *
 * Affiche l'application locale servie par le runtime Wilfrid
 * (Termux, http://127.0.0.1:8787/). Aucun pont JavaScript vers le
 * natif : toute communication passe par HTTP local. Sans serveur :
 * page d'indisponibilité honnête embarquée, jamais d'état inventé.
 */
public class MainActivity extends Activity {

    static final String WILFRID_URL = "http://127.0.0.1:8787/";
    static final int AUDIO_REQUEST = 41;

    private WebView web;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        setContentView(web);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        // Aucun pont natif : pas d'autorité côté interface.
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view,
                                                    WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.startsWith("http://127.0.0.1:")
                        || url.startsWith("http://localhost:")) {
                    return false;
                }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, int code,
                                        String description, String url) {
                view.loadData("<html><body><h1>Wilfrid indisponible</h1>"
                        + "<p>Démarre `python3 wilfrid.py --app` dans "
                        + "Termux, puis rouvre.</p></body></html>",
                        "text/html", "utf-8");
            }
        });
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(
                    new String[]{Manifest.permission.RECORD_AUDIO},
                    AUDIO_REQUEST);
        }
        web.loadUrl(WILFRID_URL);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions,
                                           int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == AUDIO_REQUEST
                && (results.length == 0
                    || results[0] != PackageManager.PERMISSION_GRANTED)) {
            Toast.makeText(this,
                    "Micro refusé : la voix reste indisponible, "
                            + "le texte reste utilisable.",
                    Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (web != null) {
            web.onPause();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) {
            web.onResume();
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
