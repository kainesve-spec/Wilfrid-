package org.wilfrid.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Scanner;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Sphère flottante Wilfrid (overlay natif, zéro moteur décisionnel).
 *
 * Affiche {@link SphereView} au-dessus des autres applications lorsque
 * l'autorisation Android est accordée. L'état affiché provient du
 * snapshot local Wilfrid (2 s) ; sans moteur : sphère OFFLINE honnête.
 * Toucher = ouvre MainActivity. Déplacement tactile, arrêt propre,
 * aucun processus après destroy. Aucune approbation émise ici.
 */
public class BubbleService extends Service {

    static final String CHANNEL = "wilfrid-bubble";
    static final int NOTICE_ID = 7;
    static final String SNAPSHOT_URL = "http://127.0.0.1:8787/snapshot";

    private WindowManager windows;
    private View bubble;
    private SphereView sphere;
    private ExecutorService poller;
    private Handler ticker;
    private volatile boolean alive;
    private volatile String visualState = "IDLE";
    private volatile float phase;
    private WindowManager.LayoutParams params;

    @Override
    public void onCreate() {
        super.onCreate();
        alive = true;
        windows = (WindowManager) getSystemService(WINDOW_SERVICE);
        sphere = new SphereView(this);
        int size = (int) (112 * getResources().getDisplayMetrics().density);
        params = new WindowManager.LayoutParams(
                size, size,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.x = 40;
        params.y = 220;
        bubble = sphere;
        bubble.setOnTouchListener(new DragTap());
        poller = Executors.newSingleThreadExecutor();
        ticker = new Handler(Looper.getMainLooper());
        startForegroundNotice();
        scheduleTick();
    }

    public static boolean overlayGranted(android.content.Context context) {
        return Settings.canDrawOverlays(context);
    }

    public static android.content.Intent overlaySettingsIntent() {
        return new android.content.Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION);
    }

    private void startForegroundNotice() {
        NotificationManager manager =
                (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(new NotificationChannel(
                    CHANNEL, "Wilfrid", NotificationManager.IMPORTANCE_LOW));
        }
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent tap = PendingIntent.getActivity(
                this, 0, open,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification notice;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            notice = new Notification.Builder(this, CHANNEL)
                    .setContentTitle("◉ Wilfrid")
                    .setContentText("Sphère active — toucher pour ouvrir")
                    .setSmallIcon(android.R.drawable.presence_online)
                    .setContentIntent(tap)
                    .build();
        } else {
            notice = new Notification.Builder(this)
                    .setContentTitle("◉ Wilfrid")
                    .setContentText("Sphère active — toucher pour ouvrir")
                    .setSmallIcon(android.R.drawable.presence_online)
                    .setContentIntent(tap)
                    .build();
        }
        startForeground(NOTICE_ID, notice);
    }

    private void scheduleTick() {
        ticker.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!alive) {
                    return;
                }
                poller.execute(new Runnable() {
                    @Override
                    public void run() {
                        final String seen = readState();
                        phase += 0.12f;
                        final float frozen = phase;
                        ticker.post(new Runnable() {
                            @Override
                            public void run() {
                                if (alive && sphere != null) {
                                    visualState = seen;
                                    sphere.setState(seen, frozen);
                                }
                            }
                        });
                    }
                });
                ticker.postDelayed(this, 2000);
            }
        }, 2000);
    }

    private String readState() {
        HttpURLConnection link = null;
        try {
            link = (HttpURLConnection) new URL(SNAPSHOT_URL).openConnection();
            link.setConnectTimeout(1500);
            link.setReadTimeout(1500);
            link.setRequestMethod("GET");
            if (link.getResponseCode() != 200) {
                return "OFFLINE";
            }
            InputStream body = link.getInputStream();
            Scanner text = new Scanner(body, "UTF-8").useDelimiter("\\A");
            String payload = text.hasNext() ? text.next() : "";
            text.close();
            int at = payload.indexOf("\"etat\"");
            if (at < 0) {
                return "OFFLINE";
            }
            int quote = payload.indexOf('"', at + 7);
            int end = payload.indexOf('"', quote + 1);
            if (quote < 0 || end < 0) {
                return "OFFLINE";
            }
            String found = payload.substring(quote + 1, end);
            return found.isEmpty() ? "OFFLINE" : found;
        } catch (Exception unexpected) {
            return "OFFLINE";
        } finally {
            if (link != null) {
                link.disconnect();
            }
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        alive = false;
        try {
            if (ticker != null) {
                ticker.removeCallbacksAndMessages(null);
            }
        } catch (Exception ignored) {
        }
        try {
            if (poller != null) {
                poller.shutdownNow();
            }
        } catch (Exception ignored) {
        }
        try {
            if (windows != null && bubble != null) {
                windows.removeView(bubble);
            }
        } catch (Exception ignored) {
        }
        bubble = null;
        sphere = null;
        windows = null;
        stopForeground(true);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private class DragTap implements View.OnTouchListener {
        private float downX;
        private float downY;
        private int startX;
        private int startY;
        private boolean moved;

        @Override
        public boolean onTouch(View view, MotionEvent event) {
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN:
                    downX = event.getRawX();
                    downY = event.getRawY();
                    startX = params.x;
                    startY = params.y;
                    moved = false;
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    float dx = event.getRawX() - downX;
                    float dy = event.getRawY() - downY;
                    if (Math.abs(dx) + Math.abs(dy) > 12) {
                        moved = true;
                    }
                    params.x = startX + (int) dx;
                    params.y = startY + (int) dy;
                    try {
                        windows.updateViewLayout(bubble, params);
                    } catch (Exception ignored) {
                    }
                    return true;
                }
                case MotionEvent.ACTION_UP:
                    if (!moved) {
                        Intent open = new Intent(BubbleService.this,
                                MainActivity.class);
                        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(open);
                    }
                    return true;
                default:
                    return false;
            }
        }
    }
}
