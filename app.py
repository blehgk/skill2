import os
from time import time, sleep

from gradio import (
    Dropdown, Number, Image, HTML, Button, Slider,
    skip, Info, Warning, Error, Blocks, Row, Column, Markdown,
)

from dbd.AI_model import AI_model
from dbd.utils.directkeys import PressKey, ReleaseKey, SPACE, is_pressed, VK_XBUTTON2
from dbd.utils.monitor import get_monitors, get_monitor_attributes, get_frame


ai_model = None


def status_badge(state):
    # state: "ON" (verde), "OFF" (rojo), "PAUSA" (amarillo)
    colors = {"ON": "#16a34a", "OFF": "#dc2626", "PAUSA": "#d97706"}
    color = colors.get(state, "#dc2626")
    return (f"<div style='text-align:center;font-size:44px;font-weight:800;"
            f"letter-spacing:3px;color:#fff;background:{color};border-radius:12px;"
            f"padding:22px 0;'>{state}</div>")


def cleanup():
    global ai_model
    if ai_model is not None:
        del ai_model
        ai_model = None
    return 0., status_badge("OFF")


def monitor(monitor_id, hit_ante):
    # Configuracion fija (sin seleccion en la UI): solo CPU, 8 threads, modelo unico.
    ai_model_path = "models/model.onnx"
    use_gpu = False
    nb_cpu_threads = 8

    if not os.path.exists(ai_model_path):
        raise Error("Invalid AI model file", duration=0)

    if monitor_id is None:
        raise Error("Invalid monitor option")

    try:
        global ai_model
        ai_model = AI_model(ai_model_path, use_gpu, nb_cpu_threads, monitor_id)
        execution_provider = ai_model.check_provider()
    except Exception as e:
        raise Error("Error when loading AI model: {}".format(e), duration=0)

    if execution_provider == "CUDAExecutionProvider":
        Info("Running AI model on GPU (success, CUDA)")
    elif execution_provider == "DmlExecutionProvider":
        Info("Running AI model on GPU (success, DirectML)")
    elif execution_provider == "TensorRT":
        Info("Running AI model on GPU (success, TensorRT)")
    else:
        Info(f"Running AI model on CPU (success, {nb_cpu_threads} threads)")
        if use_gpu:
            Warning("Could not run AI model on GPU device. Check python console logs to debug.")

    # Variables
    t0 = time()
    nb_frames = 0

    # Pause toggle with the forward side mouse button ("M4")
    PAUSE_VK = VK_XBUTTON2
    paused = False
    pause_btn_was_down = False

    yield skip(), skip(), status_badge("ON")  # bot encendido

    try:
        while True:
            # Edge detection: toggle pause only on the press (down) transition
            pause_btn_down = is_pressed(PAUSE_VK)
            if pause_btn_down and not pause_btn_was_down:
                paused = not paused
                Info("Auto skill check paused (mouse button)" if paused
                     else "Auto skill check resumed (mouse button)")
                yield (0. if paused else skip()), skip(), status_badge("PAUSA" if paused else "ON")
            pause_btn_was_down = pause_btn_down

            if paused:
                sleep(0.05)  # idle while paused, keep polling the mouse button
                t0 = time()
                nb_frames = 0
                continue

            screenshot = ai_model.grab_screenshot()
            image_pil = ai_model.screenshot_to_pil(screenshot)
            image_np = ai_model.pil_to_numpy(image_pil)
            nb_frames += 1

            pred, desc, probs, should_hit = ai_model.predict(image_np)

            if should_hit:
                # ante-frontier hit delay
                if pred == 2 and hit_ante > 0:
                    sleep(hit_ante * 0.001)

                PressKey(SPACE)
                sleep(0.005)
                ReleaseKey(SPACE)

                yield skip(), image_pil, skip()

                sleep(0.5)  # avoid hitting the same skill check multiple times
                t0 = time()
                nb_frames = 0
                continue

            # Compute fps
            t_diff = time() - t0
            if t_diff > 1.0:
                fps = round(nb_frames / t_diff, 1)
                yield fps, skip(), skip()

                t0 = time()
                nb_frames = 0

    except Exception as e:
        pass
    finally:
        print("Monitoring stopped.")


if __name__ == "__main__":
    models_folder = "models"

    fps_info = "Number of frames per second the AI model analyses the monitored frame."

    # Find available AI models (solo para validar que exista; no se elige en la UI)
    model_files = [(f, f'{models_folder}/{f}') for f in os.listdir(f"{models_folder}/") if f.endswith(".onnx") or f.endswith(".trt")]
    if len(model_files) == 0:
        raise Error(f"No AI model found in {models_folder}/", duration=0)

    # Monitor selection
    monitor_choices = get_monitors()
    def switch_monitor_cb(monitor_id):
        monitor = get_monitor_attributes(monitor_id, crop_size=520)  # 520x520 center-crop, just for the debug display
        return get_frame(monitor)

    with (Blocks(title="Auto skill check", css="footer {display: none !important}") as webui):
        Markdown("<h1 style='text-align: center;'>DBD Auto skill check</h1>", elem_id="title")

        with Row(equal_height=True):
            with Column(variant="panel", scale=2):
                with Column(variant="panel"):
                    Markdown("AI inference settings")
                    monitor_id = Dropdown(choices=monitor_choices, value=monitor_choices[0][1], label="Monitor to use")
                    hit_ante = Slider(minimum=0, maximum=50, step=5, value=3, label="Ante-frontier hit delay in ms")
                status = HTML(value=status_badge("OFF"), label="Estado del bot")
                with Column():
                    run_button = Button("RUN", variant="primary")
                    stop_button = Button("STOP", variant="stop")

            with Column(variant="panel", scale=3):
                fps = Number(label="AI model FPS", info=fps_info, interactive=False)
                image_pil = Image(label="Last hit skill check frame", height=224, interactive=False)

        monitoring = run_button.click(
            fn=monitor,
            inputs=[monitor_id, hit_ante],
            outputs=[fps, image_pil, status],
            show_progress="hidden",
        )

        stop_button.click(fn=cleanup, inputs=None, outputs=[fps, status])
        # Update the debug preview immediately when the monitor changes...
        monitor_id.change(fn=switch_monitor_cb, inputs=monitor_id, outputs=image_pil)
        # ...and also show it as soon as the web UI loads (using the default monitor).
        webui.load(fn=switch_monitor_cb, inputs=monitor_id, outputs=image_pil)

    try:
        webui.launch(show_api=False)
    except:
        print("User stopped the web UI. Please wait to cleanup resources...")
    finally:
        cleanup()
