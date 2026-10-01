package com.duoopen.lab

/**
 * Sparse event row for Transition Lab JSONL output.
 *
 * Keep the common correlation keys typed. Rare experiment-specific values can
 * be added later without turning the production controller into a lab object.
 */
internal data class TransitionEvent(
    val timeNs: Long,
    val type: String,

    val hingeSampleSequence: Long? = null,
    val measuredAngle: Float? = null,
    val visualAngle: Float? = null,
    val predictedAngle: Float? = null,
    val hingeSource: String? = null,
    val hingeSourceTimeNs: Long? = null,
    val hingeBinderArrivalTimeNs: Long? = null,
    val hingeConsumerDeliveryTimeNs: Long? = null,
    val timestampQuality: String? = null,
    val sourceToBinderLagNs: Long? = null,
    val binderToConsumerLagNs: Long? = null,
    val sourceToConsumerLagNs: Long? = null,
    val velocityDegPerSec: Float? = null,

    val direction: String? = null,
    val physicalState: String? = null,
    val generation: Long? = null,

    // Gen2 immutable ownership / ingress correlation.
    val serviceEpoch: Long? = null,
    val closeCycleId: Long? = null,
    val angleSession: Long? = null,
    val pollSequence: Long? = null,
    val sampleSequence: Long? = null,
    val shellSession: Long? = null,
    val shellRevision: Long? = null,
    val leaseId: Long? = null,
    val leaseEpoch: Long? = null,
    val contentLeaseId: Long? = null,
    val captureSequence: Long? = null,
    val hostEpoch: Long? = null,
    val presentationAttemptSequence: Long? = null,
    val renderPath: String? = null,
    val staleAtCallback: Boolean? = null,
    val rejectionReason: String? = null,

    val coverLogicalId: Int? = null,
    val innerLogicalId: Int? = null,
    val coverState: Int? = null,
    val innerState: Int? = null,
    val coverDefault: Boolean? = null,
    val innerDefault: Boolean? = null,
    val coverWidth: Int? = null,
    val coverHeight: Int? = null,
    val innerWidth: Int? = null,
    val innerHeight: Int? = null,
    val refreshRateHz: Float? = null,

    val vsyncId: Long? = null,
    val frameTimeNs: Long? = null,
    val deadlineNs: Long? = null,
    val expectedPresentNs: Long? = null,
    val predictionLeadNs: Long? = null,
    val predictionConfidence: Float? = null,

    val transactionSequence: Long? = null,
    val transactionSubmitNs: Long? = null,
    val transactionCommitNs: Long? = null,
    val transactionLatchNs: Long? = null,
    val actualPresentNs: Long? = null,

    val jankType: Int? = null,
    val scheduledAppFrameTimeNs: Long? = null,
    val actualAppFrameTimeNs: Long? = null,

    val reason: String? = null,
    val valueNs: Long? = null,
    val valueFloat: Float? = null,
)
