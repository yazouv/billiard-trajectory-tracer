"""Client OBS WebSocket pour relancer le replay mp4 automatiquement.

Côté OBS : activer "Outils > WebSocket Server Settings" (OBS 28+) et noter
host/port/password. La scène et la Media Source peuvent être créées à la main,
ou seront créées automatiquement à la première lecture si elles n'existent pas.
"""
from __future__ import annotations

import threading
from pathlib import Path

try:
    from obsws_python import EventClient, ReqClient
    _AVAILABLE = True
except ImportError:
    EventClient = None  # type: ignore
    ReqClient = None  # type: ignore
    _AVAILABLE = False


class ObsClient:
    def __init__(self):
        self._lock = threading.Lock()
        self._client = None
        self._events = None
        self._cfg = None  # (host, port, password)
        # Suivi du switch de scène pour revenir à la fin du média
        self._return_scene = None
        self._replay_scene = None
        self._replay_source = None
        self._current_scene_name = None  # mis à jour par les events OBS

    @staticmethod
    def available():
        return _AVAILABLE

    def _connect_locked(self, host, port, password):
        cfg = (host, int(port), password or "")
        if self._client is not None and self._cfg == cfg:
            return self._client
        self._disconnect_locked()
        self._client = ReqClient(host=host, port=int(port),
                                 password=password or "", timeout=3)
        self._cfg = cfg
        # Event client pour récupérer la fin de lecture
        try:
            self._events = EventClient(host=host, port=int(port),
                                       password=password or "", timeout=3)
            self._events.callback.register(self.on_media_input_playback_ended)
            self._events.callback.register(self.on_current_program_scene_changed)
            # État initial
            try:
                self._current_scene_name = self._current_scene(self._client)
            except Exception:
                self._current_scene_name = None
        except Exception as e:
            print(f"OBS: events désactivés ({e})")
            self._events = None
        return self._client

    def _disconnect_locked(self):
        if self._events is not None:
            try:
                self._events.disconnect()
            except Exception:
                pass
            self._events = None
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._cfg = None

    def disconnect(self):
        with self._lock:
            self._disconnect_locked()

    def test(self, host, port, password):
        """Renvoie (ok, message)."""
        if not _AVAILABLE:
            return False, "obsws-python n'est pas installé (pip install obsws-python)"
        try:
            cl = ReqClient(host=host, port=int(port),
                           password=password or "", timeout=3)
            v = cl.get_version()
            try:
                cl.disconnect()
            except Exception:
                pass
            return True, f"OBS {getattr(v, 'obs_version', '?')}"
        except Exception as e:
            return False, str(e)

    def _settings_for_kind(self, kind, path):
        """Construit le dict settings selon le type de source OBS."""
        if kind == "vlc_source":
            return {
                "playlist": [{"hidden": False, "selected": True, "value": path}],
                "loop": False,
                "shuffle": False,
            }
        if kind in ("browser_source",):
            return {"url": Path(path).as_uri(), "restart_when_active": True}
        # ffmpeg_source (Media Source) par défaut
        return {
            "local_file": path,
            "is_local_file": True,
            "looping": False,
            "restart_on_activate": True,
            "close_when_inactive": False,
            "clear_on_media_end": False,
        }

    def _detect_kind(self, cl, source):
        try:
            info = cl.get_input_settings(name=source)
            return getattr(info, "input_kind", None) or \
                   getattr(info, "inputKind", None)
        except Exception:
            return None

    def _current_scene(self, cl):
        try:
            r = cl.get_current_program_scene()
            # obsws-python expose plusieurs noms selon la version
            return (getattr(r, "current_program_scene_name", None) or
                    getattr(r, "scene_name", None))
        except Exception:
            return None

    def current_scene_name(self):
        return self._current_scene_name

    def on_current_program_scene_changed(self, data):
        name = (getattr(data, "scene_name", None) or
                getattr(data, "sceneName", None))
        if name:
            self._current_scene_name = name

    def on_media_input_playback_ended(self, data):
        """Callback obsws-python : nom = on_<EventName en snake_case>."""
        name = (getattr(data, "input_name", None) or
                getattr(data, "inputName", None))
        print(f"OBS: MediaInputPlaybackEnded reçu pour '{name}'.")
        if not name or name != self._replay_source:
            return
        ret = self._return_scene
        if not ret or ret == self._replay_scene:
            return
        try:
            if self._client is not None:
                self._client.set_current_program_scene(ret)
                self._current_scene_name = ret
                print(f"OBS: retour à la scène '{ret}'.")
        except Exception as e:
            print(f"OBS: retour scène impossible : {e}")
        finally:
            self._return_scene = None

    def play(self, mp4_path, host, port, password, scene, source):
        """Pointe la source `source` (dans `scene`) vers mp4_path et la relance."""
        if not _AVAILABLE:
            print("OBS: obsws-python non installé.")
            return False
        path = str(Path(mp4_path).resolve())
        try:
            with self._lock:
                cl = self._connect_locked(host, port, password)
                kind = self._detect_kind(cl, source)
                if kind is None:
                    # Source absente -> on la crée en ffmpeg_source.
                    cl.create_input(
                        scene_name=scene,
                        input_name=source,
                        input_kind="ffmpeg_source",
                        input_settings=self._settings_for_kind("ffmpeg_source", path),
                        scene_item_enabled=True,
                    )
                    kind = "ffmpeg_source"
                    print(f"OBS: source '{source}' créée (ffmpeg_source).")
                else:
                    cl.set_input_settings(
                        name=source,
                        settings=self._settings_for_kind(kind, path),
                        overlay=True,
                    )
                    print(f"OBS: source '{source}' ({kind}) -> {path}")

                # Mémorise la scène d'origine avant de basculer.
                current = self._current_scene(cl)
                if current and current != scene:
                    self._return_scene = current
                else:
                    self._return_scene = None
                self._replay_scene = scene
                self._replay_source = source

                try:
                    cl.set_current_program_scene(scene)
                    self._current_scene_name = scene
                except Exception as e:
                    print(f"OBS: scène '{scene}' introuvable ? {e}")

                # Déclenche la lecture sur les inputs qui supportent l'action média.
                if kind in ("ffmpeg_source", "vlc_source"):
                    cl.trigger_media_input_action(
                        source, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
                else:
                    print(f"OBS: type '{kind}' ne supporte pas RESTART, "
                          "utilise une Media Source (ffmpeg_source) ou VLC source.")
            return True
        except Exception as e:
            print(f"OBS: erreur de lecture : {e}")
            self.disconnect()
            return False

    def stop_and_return(self, host, port, password, source):
        """Coupe la lecture en cours et rebascule sur la scène mémorisée."""
        if not _AVAILABLE:
            return False
        try:
            with self._lock:
                cl = self._connect_locked(host, port, password)
                try:
                    cl.trigger_media_input_action(
                        source, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
                except Exception as e:
                    print(f"OBS: stop média impossible : {e}")
                ret = self._return_scene
                if ret and ret != self._replay_scene:
                    try:
                        cl.set_current_program_scene(ret)
                        self._current_scene_name = ret
                        print(f"OBS: retour manuel à la scène '{ret}'.")
                    except Exception as e:
                        print(f"OBS: retour scène impossible : {e}")
                self._return_scene = None
            return True
        except Exception as e:
            print(f"OBS: stop_and_return erreur : {e}")
            self.disconnect()
            return False

    def stop_and_return_async(self, host, port, password, source):
        threading.Thread(
            target=self.stop_and_return,
            args=(host, port, password, source),
            daemon=True,
        ).start()

    def play_async(self, mp4_path, host, port, password, scene, source,
                   on_done=None):
        def run():
            ok = self.play(mp4_path, host, port, password, scene, source)
            if on_done is not None:
                try:
                    on_done(ok)
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True).start()
