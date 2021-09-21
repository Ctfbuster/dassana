package app.dassana.core.workflow.processor;

import static app.dassana.core.workflow.processor.Decorator.DASSANA_KEY;

import app.dassana.core.workflow.model.WorkflowOutputWithRisk;
import java.util.Optional;
import java.util.UUID;
import javax.inject.Inject;
import javax.inject.Singleton;
import org.joda.time.DateTime;
import org.joda.time.DateTimeZone;
import org.json.JSONObject;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

@Singleton
public class S3Manager {

  @Inject private S3Client s3Client;

  private final String dassanaBucket = System.getenv().get("dassanaBucket");

  public String uploadedToS3(Optional<WorkflowOutputWithRisk> normalizationResult,
      String jsonToUpload) {

    DateTime now = DateTime.now(DateTimeZone.UTC);

    int min = now.minuteOfHour().get();
    int hour = now.hourOfDay().get();
    int day = now.dayOfMonth().get();
    int month = now.monthOfYear().get();
    int year = now.year().get();

    String alertsPrefix = "alerts".concat(
        "/year=".concat(String.valueOf(year)).concat(
            "/month=").concat(String.valueOf(month)).concat(
            "/day=").concat(String.valueOf(day)).concat(
            "/hour=").concat(String.valueOf(hour)).concat(
            "/min=").concat(String.valueOf(min)));

    String path;
    if (normalizationResult.isEmpty()) {
      path = alertsPrefix.concat("/unprocessed/").concat(UUID.randomUUID().toString());
    } else {
      WorkflowOutputWithRisk workflowOutputWithRisk = normalizationResult.get();

      path = alertsPrefix.concat(
          "/csp=").concat((String) workflowOutputWithRisk.getOutput().get("csp")).concat(
          "/resource_container=")
          .concat((String) workflowOutputWithRisk.getOutput().get("resourceContainer")).concat(
              "/region=").concat((String) workflowOutputWithRisk.getOutput().get("region")).concat(
              "/normalizer_workflow=").concat(workflowOutputWithRisk.getWorkflowId()).concat(
              "/alertid=").concat((String) workflowOutputWithRisk.getOutput().get("alertId"));


    }

    PutObjectRequest putObjectRequest = PutObjectRequest.builder().bucket(dassanaBucket).
        key(path).
        build();

    s3Client.putObject(putObjectRequest, RequestBody.fromBytes(jsonToUpload.getBytes()));

    if (normalizationResult.isPresent()) {
      JSONObject dassanaDecoratedJsonObj = new JSONObject(jsonToUpload);
      JSONObject updatedDassanaObj = dassanaDecoratedJsonObj.getJSONObject(DASSANA_KEY)
          .put("alertKey", "s3://".concat(dassanaBucket).concat("/").concat(path));
      dassanaDecoratedJsonObj.put(DASSANA_KEY, updatedDassanaObj);
      return dassanaDecoratedJsonObj.toString();
    } else {
      return jsonToUpload;
    }


  }

}
