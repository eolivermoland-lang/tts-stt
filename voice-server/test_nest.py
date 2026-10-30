import time, pychromecast

NEST_NAVN = "Entryway speaker"

casts, browser = pychromecast.get_listed_chromecasts(friendly_names=[NEST_NAVN])
cast = casts[0]
cast.wait()
cast.quit_app()
time.sleep(2)
cast.set_volume(0.5)
mc = cast.media_controller
mc.play_media("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", "audio/mp3")
mc.block_until_active(timeout=15)
for _ in range(10):
    time.sleep(1)
    print(mc.status.player_state, mc.status.idle_reason)
cast.quit_app()
browser.stop_discovery()