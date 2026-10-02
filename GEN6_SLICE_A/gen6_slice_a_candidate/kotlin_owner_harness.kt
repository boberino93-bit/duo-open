package com.duoopen.overlay
fun main() {
    val owner=Fold7Gen6OpeningAttemptOwner(7L)
    check(owner.onWakeHint(0,1,10L)?.id==1L)
    check(owner.onWakeHint(0,2,11L)==null)
    check(owner.markSemanticAccepted(44L)?.semanticGeneration==44L)
    check(owner.finish("corroborated-closed",20L)?.attempt?.id==1L)
    check(owner.onWakeHint(0,2,30L)?.id==2L)
    println("GEN6 SLICE A KOTLIN OWNER HARNESS: PASS")
}
