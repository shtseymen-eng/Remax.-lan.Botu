from __future__ import annotations
import unittest
from collections import defaultdict, deque

from remax_bot.whatsapp_webengine import (
    EmbeddedWhatsAppBot, MAX_INTRO, MessageRouter, classify_command
)

def snapshot(chat_id="group-1", title="Bot deneme", messages=None):
    return {"chat":{"id":chat_id,"title":title},"messages":list(messages or [])}

class FakePage:
    def __init__(self):
        self.responses=defaultdict(deque)
        self.fallback=deque()
        self.calls=[]
    def add(self,script,*responses):
        self.responses[script].extend(responses)
    def add_any(self,*responses):
        self.fallback.extend(responses)
    def runJavaScript(self,script,callback=None):
        self.calls.append(script)
        q=self.responses[script]
        value=q.popleft() if q else (self.fallback.popleft() if self.fallback else None)
        if callback: callback(value)

class RuntimeTests(unittest.TestCase):
    def test_max_start_aliases(self):
        self.assertEqual(classify_command("#Max başla"),"start")
        self.assertEqual(classify_command("#MAX BAŞLAT"),"start")
        self.assertEqual(classify_command("#bot başlat"),"query")

    def test_first_snapshot_is_only_primed(self):
        router=MessageRouter(lambda x:"x")
        result=router.process(snapshot(messages=[{"id":"old","text":"#Max başla"}]))
        self.assertEqual(result.replies,[])
        self.assertFalse(router.active)

    def test_new_max_start_activates(self):
        router=MessageRouter(lambda x:"x")
        router.process(snapshot())
        result=router.process(snapshot(messages=[{"id":"start","text":"#Max başla"}]))
        self.assertEqual(result.replies,[MAX_INTRO])
        self.assertTrue(router.active)

    def test_query_is_answered_once(self):
        router=MessageRouter(lambda text:f"Sonuç: {text}")
        router.process(snapshot())
        router.process(snapshot(messages=[{"id":"start","text":"#Max başla"}]))
        cmd={"id":"q1","text":"#izmit kiralık 55 bin"}
        first=router.process(snapshot(messages=[cmd]))
        second=router.process(snapshot(messages=[cmd]))
        self.assertEqual(first.replies,["Max: Sonuç: #izmit kiralık 55 bin"])
        self.assertEqual(second.replies,[])

    def test_constructor_starts_listener_automatically(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(lambda _:"",page=page,schedule=lambda _ms,fn:fn())
        self.assertTrue(bot.running)

    def test_user_start_activates_bot_immediately(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(lambda _:"",page=page,schedule=lambda _ms,fn:fn())
        self.assertFalse(bot.active)

        bot.start("Max deneme")

        self.assertTrue(bot.active)

    def test_first_snapshot_after_user_start_answers_latest_command_once(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(lambda text:f"Sonuç: {text}",page=page,schedule=lambda _ms,fn:fn())
        bot.start("Max deneme")

        first=bot.router.process(snapshot(
            title="Max deneme",
            messages=[
                {"id":"old","text":"#eski komut"},
                {"id":"fresh","text":"#izmit kiralık"},
            ],
        ))
        repeated=bot.router.process(snapshot(
            title="Max deneme",
            messages=[{"id":"fresh","text":"#izmit kiralık"}],
        ))

        self.assertEqual(first.replies,["Max: Sonuç: #izmit kiralık"])
        self.assertEqual(repeated.replies,[])
        self.assertEqual(first.status,"Max aktif - Max deneme dinleniyor")

    def test_saved_active_state_is_restored_without_replaying_history(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(
            lambda text:f"Sonuç: {text}",
            page=page,
            schedule=lambda _ms,fn:fn(),
            initial_group="Max deneme",
            start_active=True,
        )

        first=bot.router.process(snapshot(
            title="Max deneme",
            messages=[{"id":"old","text":"#eski komut"}],
        ))

        self.assertTrue(bot.active)
        self.assertEqual(bot.router.configured_group,"Max deneme")
        self.assertEqual(first.replies,[])
        self.assertEqual(first.status,"Max aktif - Max deneme dinleniyor")

    def test_stop_keeps_reader_alive_for_future_max_start(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(lambda _:"",page=page,schedule=lambda _ms,fn:fn())
        bot.router.active=True
        bot.stop()
        self.assertTrue(bot.running)
        self.assertFalse(bot.active)

    def test_restarting_same_group_keeps_reader_history_and_answers_new_command(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(lambda text:f"Sonuç: {text}",page=page,schedule=lambda _ms,fn:fn())
        bot.start("Bot deneme")
        bot.router.process(snapshot(title="Bot deneme"))

        bot.start("  Bot deneme  ")
        result=bot.router.process(snapshot(title="Bot deneme",messages=[{"id":"own-start","text":"#max başla"}]))

        self.assertEqual(result.replies,[MAX_INTRO])
        self.assertTrue(bot.active)

    def test_set_group_searches_only_inside_whatsapp_sidebar(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(lambda _:"",page=page,schedule=lambda _ms,fn:fn())
        before=len(page.calls)
        bot.set_group("Bot deneme")
        new_calls=page.calls[before:]
        self.assertGreaterEqual(len(new_calls),1)
        self.assertTrue(any('const side=' in script for script in new_calls))
        self.assertTrue(any('const wanted="Bot deneme"' in script for script in new_calls))

    def test_send_single_message(self):
        page=FakePage()
        bot=EmbeddedWhatsAppBot(lambda _:"",page=page,schedule=lambda _ms,fn:fn())
        page.add_any(True)
        page.add(EmbeddedWhatsAppBot.CLICK_SEND_JS,True)
        page.add(EmbeddedWhatsAppBot.COMPOSER_EMPTY_JS,True)
        sent=[]
        bot.sent.connect(lambda _channel,text:sent.append(text))
        bot._send("Max: Tek cevap")
        self.assertEqual(sent,["Max: Tek cevap"])

if __name__=="__main__":
    unittest.main()
