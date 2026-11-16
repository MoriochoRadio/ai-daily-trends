"""YouTube 수집의 재시도·채널별 격리·이월(빈 섹션 방지)·연속 실패 알림 테스트 — 네트워크 없음.

실행: python -m unittest discover -s tests
"""
import json, pathlib, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import collect  # noqa: E402
import summarize  # noqa: E402

TODAY = "2026-11-16"
CIDS = [cid for cid, _, _ in collect.YT_CHANNELS]
NAMES = {cid: name for cid, name, _ in collect.YT_CHANNELS}


def feed(cid, published="2026-11-15T10:00:00+00:00", title="New video"):
    """YouTube 채널 Atom 피드 모양(채널 자체 <published> 다음에 entry 들이 온다)."""
    return (f'<feed><title>{NAMES.get(cid, cid)}</title><published>2015-01-01T00:00:00+00:00</published>'
            f'<entry><title>{title} {cid}</title>'
            f'<link rel="alternate" href="https://www.youtube.com/watch?v={cid[-4:]}"/>'
            f'<published>{published}</published>'
            f'<media:description>desc &amp; more</media:description></entry>'
            f'<entry><title>older</title><link rel="alternate" href="https://x/old"/>'
            f'<published>2026-01-01T00:00:00+00:00</published></entry></feed>')


class FakeFeeds:
    """channel_id 별로 응답 상태를 차례대로 돌려준다. 목록이 끝나면 마지막 상태를 반복."""

    def __init__(self, plan, default=200):
        self.plan = plan
        self.default = default
        self.calls = {}

    def __call__(self, url, timeout=20):
        cid = url.rsplit("=", 1)[1]
        n = self.calls.get(cid, 0)
        self.calls[cid] = n + 1
        seq = self.plan.get(cid, [self.default])
        status = seq[min(n, len(seq) - 1)]
        if status == 200:
            return 200, feed(cid)
        if status == "garbage":
            return 200, "<html>not a feed</html>"
        return status, ""


def run_fetch(plan, default=200):
    fake = FakeFeeds(plan, default)
    with mock.patch.object(collect, "_get_feed", fake), \
         mock.patch.object(collect.time, "sleep") as slept:
        got, why = collect._fetch_yt_channels(TODAY)
    return got, why, fake, slept


class FetchRetryTest(unittest.TestCase):
    def test_transient_404_and_5xx_are_retried_until_success(self):
        a, b = CIDS[0], CIDS[1]
        got, why, fake, slept = run_fetch({a: [404, 404, 200], b: [503, 200]})
        self.assertEqual(len(got), len(CIDS))
        self.assertEqual(why, {})
        self.assertEqual(fake.calls[a], 3)
        self.assertEqual(fake.calls[b], 2)
        # 성공한 채널은 다시 요청하지 않는다
        self.assertEqual(fake.calls[CIDS[2]], 1)
        # 재시도 라운드는 2번만 돌았다 → 대기도 앞의 두 값뿐
        self.assertEqual([c.args[0] for c in slept.call_args_list], list(collect.YT_ROUND_WAITS[:2]))

    def test_429_and_network_error_are_retried(self):
        a, b = CIDS[0], CIDS[1]
        got, _, fake, _ = run_fetch({a: [429, 200], b: [0, 0, 200]})
        self.assertIn(a, got)
        self.assertIn(b, got)

    def test_retries_are_bounded_and_failure_is_isolated(self):
        dead = CIDS[3]
        got, why, fake, slept = run_fetch({dead: [404]})
        self.assertNotIn(dead, got)
        self.assertEqual(len(got), len(CIDS) - 1)          # 다른 채널은 영향 없음
        self.assertEqual(why, {dead: "404"})
        self.assertEqual(fake.calls[dead], len(collect.YT_ROUND_WAITS) + 1)
        self.assertLessEqual(sum(c.args[0] for c in slept.call_args_list), 120)

    def test_non_transient_status_is_not_retried(self):
        gone = CIDS[4]
        got, why, fake, _ = run_fetch({gone: [403]})
        self.assertNotIn(gone, got)
        self.assertEqual(fake.calls[gone], 1)
        self.assertEqual(why[gone], "403")

    def test_unparseable_200_counts_as_failure_without_retry(self):
        odd = CIDS[5]
        got, why, fake, _ = run_fetch({odd: ["garbage"]})
        self.assertNotIn(odd, got)
        self.assertEqual(why[odd], "형식")
        self.assertEqual(fake.calls[odd], 1)

    def test_no_sleep_when_everything_succeeds_first_time(self):
        got, _, _, slept = run_fetch({})
        self.assertEqual(len(got), len(CIDS))
        slept.assert_not_called()

    def test_parsed_item_shape(self):
        got, _, _, _ = run_fetch({})
        v = got[CIDS[0]]
        self.assertEqual(v["channel"], NAMES[CIDS[0]])
        self.assertEqual(v["channel_id"], CIDS[0])
        self.assertEqual(v["published"], "2026-11-15")      # 채널 자체 published 가 아니라 영상 것
        self.assertEqual(v["fetched"], TODAY)
        self.assertEqual(v["desc"], "desc & more")
        self.assertTrue(v["url"].startswith("https://www.youtube.com/watch?v="))


def prev_item(cid, published="2026-11-10", fetched="2026-11-15", **kw):
    return {"title": "old " + cid, "channel": NAMES[cid], "channel_id": cid,
            "url": "https://www.youtube.com/watch?v=old" + cid[-4:], "published": published,
            "desc": "", "fetched": fetched, "title_ko": "이전 제목", **kw}


class MergeTest(unittest.TestCase):
    def fresh(self, cids, published="2026-11-15"):
        return {c: {**prev_item(c, published=published, fetched=TODAY), "title": "new " + c} for c in cids}

    def test_failed_channel_keeps_previous_video_marked_carried_with_real_date(self):
        ok, failed = CIDS[0], CIDS[1]
        vids = collect.merge_youtube(self.fresh([ok]), [prev_item(failed, published="2026-11-02")], TODAY)
        self.assertEqual([v["channel_id"] for v in vids], [ok, failed])
        carried = vids[1]
        self.assertTrue(carried["carried"])
        self.assertEqual(carried["published"], "2026-11-02")
        self.assertNotIn("carried", vids[0])

    def test_fresh_video_wins_over_previous_one_for_same_channel(self):
        c = CIDS[0]
        vids = collect.merge_youtube(self.fresh([c]), [prev_item(c)], TODAY)
        self.assertEqual(len(vids), 1)
        self.assertEqual(vids[0]["title"], "new " + c)

    def test_legacy_or_unknown_channel_items_are_not_carried(self):
        legacy = {"title": "3B1B short", "channel": "Andrej Karpathy", "url": "https://x", "published": "2026-10-25"}
        unknown = {**prev_item(CIDS[0]), "channel_id": "UCnotconfigured"}
        vids = collect.merge_youtube(self.fresh([CIDS[1]]), [legacy, unknown], TODAY)
        self.assertEqual([v["channel_id"] for v in vids], [CIDS[1]])

    def test_partial_day_drops_carry_older_than_limit(self):
        stale = prev_item(CIDS[2], fetched="2026-11-01")     # 15일 전에 받은 것
        recent = prev_item(CIDS[3], fetched="2026-11-12")
        vids = collect.merge_youtube(self.fresh([CIDS[0]]), [stale, recent], TODAY)
        self.assertEqual({v["channel_id"] for v in vids}, {CIDS[0], CIDS[3]})

    def test_zero_fresh_keeps_all_previous_videos_regardless_of_age(self):
        prev = [prev_item(CIDS[2], fetched="2026-10-01"), prev_item(CIDS[3])]
        vids = collect.merge_youtube({}, prev, TODAY)
        self.assertEqual(len(vids), 2)
        self.assertTrue(all(v["carried"] for v in vids))

    def test_limit_and_sort_by_published(self):
        fresh = {c: {**prev_item(c, fetched=TODAY), "published": f"2026-11-{i + 1:02d}"}
                 for i, c in enumerate(CIDS)}
        vids = collect.merge_youtube(fresh, [], TODAY, limit=9)
        self.assertEqual(len(vids), 9)
        dates = [v["published"] for v in vids]
        self.assertEqual(dates, sorted(dates, reverse=True))


class YoutubeEndToEndTest(unittest.TestCase):
    def test_all_channels_failing_publishes_previous_videos_not_empty(self):
        prev = [prev_item(CIDS[0]), prev_item(CIDS[1])]
        with mock.patch.object(collect, "_get_feed", FakeFeeds({}, default=404)), \
             mock.patch.object(collect.time, "sleep"), mock.patch("builtins.print"):
            vids, ok = collect.youtube(prev, today=TODAY)
        self.assertEqual(ok, 0)
        self.assertEqual(len(vids), 2)
        self.assertTrue(all(v["carried"] for v in vids))

    def test_no_previous_data_and_all_failing_gives_empty_without_error(self):
        with mock.patch.object(collect, "_get_feed", FakeFeeds({}, default=500)), \
             mock.patch.object(collect.time, "sleep"), mock.patch("builtins.print"):
            vids, ok = collect.youtube(None, today=TODAY)
        self.assertEqual((vids, ok), ([], 0))


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / "health.json"
        self.path.write_text(json.dumps({"summary_zero_streak": 1, "last_model": "m", "last_problem": None}),
                             encoding="utf-8")
        self.patches = [mock.patch.object(collect, "HEALTH_PATH", self.path),
                        mock.patch.object(summarize, "HEALTH_PATH", self.path)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_alert_only_after_streak_of_total_failures(self):
        alerts = [collect.record_youtube_health(0) for _ in range(collect.YT_ZERO_STREAK_ALERT)]
        self.assertEqual(alerts[:-1], [""] * (collect.YT_ZERO_STREAK_ALERT - 1))
        self.assertIn("YouTube", alerts[-1])
        self.assertEqual(self.read()["youtube_zero_streak"], collect.YT_ZERO_STREAK_ALERT)
        self.assertEqual(self.read()["summary_zero_streak"], 1)      # 요약 쪽 키는 건드리지 않음

    def test_any_channel_success_resets_streak(self):
        collect.record_youtube_health(0)
        collect.record_youtube_health(0)
        self.assertEqual(collect.record_youtube_health(1), "")
        self.assertEqual(self.read()["youtube_zero_streak"], 0)

    def test_summarize_keeps_youtube_streak(self):
        collect.record_youtube_health(0)
        summarize.record_health(5, None, "m2")
        h = self.read()
        self.assertEqual(h["youtube_zero_streak"], 1)
        self.assertEqual(h["summary_zero_streak"], 0)
        self.assertEqual(h["last_model"], "m2")

    def test_emit_alert_writes_github_output_only_when_message(self):
        out = pathlib.Path(self.tmp.name) / "out.txt"
        with mock.patch.dict("os.environ", {"GITHUB_OUTPUT": str(out)}), mock.patch("builtins.print"):
            collect.emit_alert("")
            self.assertFalse(out.exists())
            collect.emit_alert("help")
        self.assertEqual(out.read_text(encoding="utf-8"), "alert=help\n")


class RedditFetchUnchangedTest(unittest.TestCase):
    """공용 _get_feed 로 바꾼 뒤에도 Reddit 은 기존처럼 429 만 재시도한다."""

    def test_reddit_retries_429_only(self):
        seq = iter([(429, ""), (200, "ok")])
        with mock.patch.object(collect, "_get_feed", lambda url: next(seq)), \
             mock.patch.object(collect.time, "sleep"):
            self.assertEqual(collect._fetch_rss("u"), "ok")
        calls = []
        with mock.patch.object(collect, "_get_feed", lambda url: calls.append(url) or (404, "")), \
             mock.patch.object(collect.time, "sleep"):
            self.assertEqual(collect._fetch_rss("u"), "")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
