package org.wilfrid.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.util.AttributeSet;
import android.view.View;

/**
 * Sphère Wilfrid : halo, sphère bleue, noyau, anneaux, yeux, bouche.
 * Reçoit un état (chaîne) déjà établi par le moteur ; ne décide rien.
 * Animation sobre pilotée par un temps fourni, jamais en boucle libre
 * interne : l'hôte appelle {@code tick()} à intervalle raisonnable.
 */
public class SphereView extends View {

    private String state = "IDLE";
    private float phase = 0f;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

    public SphereView(Context context) {
        super(context);
    }

    public SphereView(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    public void setState(String visualState, float animationPhase) {
        state = visualState != null ? visualState : "IDLE";
        phase = animationPhase;
        invalidate();
    }

    public String getVisualState() {
        return state;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float cx = getWidth() / 2f;
        float cy = getHeight() / 2f;
        float radius = Math.min(cx, cy) * 0.62f;
        boolean dim = "OFFLINE".equals(state) || "INTERRUPTED".equals(state);
        boolean alert = "WAITING_APPROVAL".equals(state);
        boolean happy = "SUCCESS".equals(state);
        boolean bad = "ERROR".equals(state);

        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(60, 80, 140, 255));
        canvas.drawCircle(cx, cy, radius * 1.25f, paint);

        RadialGradient sphere = new RadialGradient(
                cx, cy, radius,
                new int[]{Color.rgb(140, 190, 255), Color.rgb(40, 90, 220),
                        Color.rgb(10, 20, 60)},
                new float[]{0f, 0.7f, 1f}, Shader.TileMode.CLAMP);
        paint.setShader(sphere);
        if (dim) {
            paint.setAlpha(120);
        }
        canvas.drawCircle(cx, cy, radius, paint);
        paint.setShader(null);
        paint.setAlpha(255);

        float coreR = radius * (bad ? 0.18f : 0.24f);
        paint.setColor(happy ? Color.rgb(160, 255, 200)
                : Color.rgb(200, 230, 255));
        canvas.drawCircle(cx, cy, coreR, paint);

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(radius * 0.045f);
        paint.setColor(alert ? Color.rgb(255, 210, 120)
                : Color.rgb(120, 180, 255));
        RectF orbit = new RectF(cx - radius * 1.15f, cy - radius * 0.45f,
                cx + radius * 1.15f, cy + radius * 0.45f);
        canvas.save();
        canvas.rotate(phase * 12f, cx, cy);
        canvas.drawOval(orbit, paint);
        canvas.restore();
        canvas.save();
        canvas.rotate(-phase * 8f + 40f, cx, cy);
        RectF orbit2 = new RectF(cx - radius * 0.9f, cy - radius * 1.1f,
                cx + radius * 0.9f, cy + radius * 1.1f);
        canvas.drawOval(orbit2, paint);
        canvas.restore();

        float eyeY = cy - radius * 0.12f;
        float eyeDx = radius * 0.30f;
        float eyeR = radius * 0.13f;
        paint.setStyle(Paint.Style.FILL);
        if ("OFFLINE".equals(state)) {
            paint.setColor(Color.rgb(20, 30, 60));
            canvas.drawRect(cx - eyeDx - eyeR, eyeY - eyeR * 0.15f,
                    cx - eyeDx + eyeR, eyeY + eyeR * 0.15f, paint);
            canvas.drawRect(cx + eyeDx - eyeR, eyeY - eyeR * 0.15f,
                    cx + eyeDx + eyeR, eyeY + eyeR * 0.15f, paint);
        } else {
            boolean wide = happy || "SURPRISE".equals(state);
            float hr = wide ? eyeR * 1.2f : eyeR;
            paint.setColor(Color.WHITE);
            canvas.drawCircle(cx - eyeDx, eyeY, hr, paint);
            canvas.drawCircle(cx + eyeDx, eyeY, hr, paint);
            paint.setColor(Color.rgb(5, 8, 20));
            canvas.drawCircle(cx - eyeDx, eyeY, hr * 0.45f, paint);
            canvas.drawCircle(cx + eyeDx, eyeY, hr * 0.45f, paint);
            paint.setColor(Color.WHITE);
            canvas.drawCircle(cx - eyeDx - hr * 0.15f, eyeY - hr * 0.15f,
                    hr * 0.14f, paint);
            canvas.drawCircle(cx + eyeDx - hr * 0.15f, eyeY - hr * 0.15f,
                    hr * 0.14f, paint);
        }

        float mouthY = cy + radius * 0.34f;
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(radius * 0.035f);
        paint.setColor(Color.rgb(10, 16, 40));
        if (happy) {
            RectF smile = new RectF(cx - radius * 0.16f, mouthY - radius * 0.10f,
                    cx + radius * 0.16f, mouthY + radius * 0.10f);
            canvas.drawArc(smile, 15f, 150f, false, paint);
        } else if (bad) {
            canvas.drawLine(cx - radius * 0.12f, mouthY,
                    cx + radius * 0.12f, mouthY, paint);
        } else {
            RectF calm = new RectF(cx - radius * 0.12f, mouthY - radius * 0.06f,
                    cx + radius * 0.12f, mouthY + radius * 0.06f);
            canvas.drawArc(calm, 25f, 130f, false, paint);
        }

        if ("WAITING_APPROVAL".equals(state)) {
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(radius * 0.03f);
            paint.setColor(Color.rgb(255, 210, 120));
            float pulse = radius * (1.3f + 0.05f * (float) Math.sin(phase));
            canvas.drawCircle(cx, cy, pulse, paint);
        }
    }
}
