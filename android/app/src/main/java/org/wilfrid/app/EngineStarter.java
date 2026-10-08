package org.wilfrid.app;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;

/**
 * Démarrage best-effort du moteur Wilfrid via Termux:RUN_COMMAND.
 *
 * Ne prétend jamais que le moteur tourne : le résultat se vérifie par
 * le snapshot local (/snapshot). Sans Termux:API, retour honnête
 * d'indisponibilité. Aucune donnée transmise, aucune autorité.
 */
public final class EngineStarter {

    static final String RUN_ACTION = "com.termux.RUN_COMMAND";
    static final String EXTRA_COMMAND =
            "com.termux.RUN_COMMAND_PATH";
    static final String EXTRA_ARGS =
            "com.termux.RUN_COMMAND_ARGUMENTS";
    static final String EXTRA_BACKGROUND =
            "com.termux.RUN_COMMAND_BACKGROUND";

    private EngineStarter() {
    }

    public static String requestStart(Context context) {
        Intent launch = new Intent();
        launch.setAction(RUN_ACTION);
        launch.setClassName("com.termux",
                "com.termux.app.RunCommandService");
        launch.putExtra(EXTRA_COMMAND,
                "/data/data/com.termux/files/home/.termux/boot/wilfrid.sh");
        launch.putExtra(EXTRA_ARGS, new String[0]);
        launch.putExtra(EXTRA_BACKGROUND, true);
        try {
            ComponentName target = launch.resolveActivity(
                    context.getPackageManager());
            if (target == null) {
                return "termux-api-absent";
            }
            context.startService(launch);
            return "demande-envoyee";
        } catch (SecurityException denied) {
            return "permission-refusee";
        } catch (Exception unexpected) {
            return "demarrage-impossible:" + unexpected.getClass()
                    .getSimpleName();
        }
    }
}
