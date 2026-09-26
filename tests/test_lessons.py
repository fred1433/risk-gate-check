import unittest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate.lessons import destructive_registration, with_lessons

REDIS = """diff --git a/src/M/Startup.cs b/src/M/Startup.cs
--- a/src/M/Startup.cs
+++ b/src/M/Startup.cs
@@ -126,6 +127,9 @@
+            services.RemoveAll<IConfigureOptions<KeyManagementOptions>>();
             services.AddTransient<IConfigureOptions<KeyManagementOptions>, RedisKeyManagementOptionsSetup>();
"""
class Lessons(unittest.TestCase):
    def test_added_removeall_escalates(self):
        self.assertEqual(destructive_registration(REDIS), ["src/M/Startup.cs"])
        self.assertEqual(with_lessons({"decision": "ALLOW", "reasons": []}, REDIS)["decision"], "REVIEW_REQUIRED")
    def test_removed_removeall_is_not_destructive(self):
        self.assertEqual(destructive_registration(REDIS.replace("+            services.RemoveAll", "-            services.RemoveAll")), [])
    def test_plain_registration_untouched(self):
        d = REDIS.replace("services.RemoveAll<IConfigureOptions<KeyManagementOptions>>();", "services.AddScoped<IFoo, Foo>();")
        self.assertEqual(with_lessons({"decision": "ALLOW", "reasons": []}, d)["decision"], "ALLOW")
    def test_real_18508_snapshot_if_present(self):
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snapshots/18508/diff.patch")
        if not os.path.exists(p): self.skipTest("snapshots not built")
        self.assertEqual(len(destructive_registration(open(p).read())), 2)

if __name__ == "__main__":
    unittest.main()
