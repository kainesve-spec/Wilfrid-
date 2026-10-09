package org.wilfrid.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.view.Menu;
import android.view.MenuItem;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
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
        // Micro WebView : getUserMedia exige l'accord explicite de la
        // WebView (RESOURCE_AUDIO_CAPTURE), en plus de la permission
        // Android RECORD_AUDIO. Sans ceci, l'écoute reste muette.
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                String[] wanted = request.getResources();
                boolean audio = false;
                for (String name : wanted) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(
                            name)) {
                        audio = true;
                    }
                }
                boolean granted = checkSelfPermission(
                        Manifest.permission.RECORD_AUDIO)
                        == PackageManager.PERMISSION_GRANTED;
                if (audio && granted) {
                    request.grant(new String[]{
                            PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                } else {
                    request.deny();
                }
            }
        });
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
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, "Sphère flottante");
        menu.add(0, 2, 0, "Retirer la sphère");
        menu.add(0, 3, 0, "Autoriser l'overlay");
        menu.add(0, 4, 0, "Démarrer le moteur");
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        int code = item.getItemId();
        if (code == 1) {
            if (!BubbleService.overlayGranted(this)) {
                Toast.makeText(this,
                        "Overlay non accordé : ouvre les paramètres "
                                + "via « Autoriser l'overlay ».",
                        Toast.LENGTH_LONG).show();
                return true;
            }
            startService(new Intent(this, BubbleService.class));
            return true;
        }
        if (code == 2) {
            stopService(new Intent(this, BubbleService.class));
            return true;
        }
        if (code == 3) {
            startActivity(BubbleService.overlaySettingsIntent());
            return true;
        }
        if (code == 4) {
            String done = EngineStarter.requestStart(this);
            Toast.makeText(this, "Moteur : " + done, Toast.LENGTH_LONG)
                    .show();
            web.reload();
            return true;
        }
        return super.onOptionsItemSelected(item);
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
