package com.duoopen.debug

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

class DebugBundleUploaderTest {
    @Test
    fun sha256MatchesKnownVector() {
        val file = File.createTempFile("duoopen-sha", ".txt")
        try {
            file.writeText("abc")
            assertEquals(
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                DebugBundleUploader.sha256(file),
            )
        } finally {
            file.delete()
        }
    }
}
