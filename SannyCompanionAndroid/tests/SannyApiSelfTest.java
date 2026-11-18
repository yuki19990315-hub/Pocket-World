import com.sanny.pocketworld.SannyApi;
import java.io.ByteArrayInputStream;
import java.io.IOException;

public class SannyApiSelfTest {
    private static void check(boolean value) {
        if (!value) throw new AssertionError("Sanny API test failed");
    }
    public static void main(String[] args) throws IOException {
        check("index.html".equals(SannyApi.uploadName("index.html")));
        check("world_model.py".equals(SannyApi.uploadName("world_model.py")));
        check("assets/tree.png".equals(SannyApi.uploadName("tree.png")));
        check(SannyApi.uploadName("main.py") == null);
        check(SannyApi.uploadName("../main.py") == null);
        check(SannyApi.uploadName("huge.zip") == null);
        check(SannyApi.readLimited(new ByteArrayInputStream("abc".getBytes())).length == 3);
        try {
            SannyApi.readLimited(new ByteArrayInputStream(new byte[SannyApi.MAX_FILE + 1]));
            throw new AssertionError("Oversized file accepted");
        } catch (IOException expected) { /* correct */ }
        String schedule = SannyApi.scheduleJson(true, "08:30", "18:45", 1790000000L);
        check(schedule.contains("\"clock\":1790000000"));
        check(schedule.contains("\"exclude_jp_holidays\":true"));
        check(schedule.contains("\"wake\":\"08:30\""));
        for (int invalid : new int[]{0, 101}) {
            try {
                SannyApi.setDisplayBrightness(invalid, "test");
                throw new AssertionError("Out-of-range brightness accepted");
            } catch (IOException expected) { /* reject before any network call */ }
        }
        System.out.println("SannyApiSelfTest: 13 checks passed");
    }
}
