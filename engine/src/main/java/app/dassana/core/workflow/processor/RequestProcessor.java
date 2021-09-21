package app.dassana.core.workflow.processor;

import static app.dassana.core.contentmanager.ContentManager.GENERAL_CONTEXT;
import static app.dassana.core.contentmanager.ContentManager.POLICY_CONTEXT;
import static app.dassana.core.contentmanager.ContentManager.RESOURCE_CONTEXT;

import app.dassana.core.contentmanager.ContentManagerApi;
import app.dassana.core.launch.ApiHandler;
import app.dassana.core.launch.SqsHandler;
import app.dassana.core.launch.model.ProcessingResponse;
import app.dassana.core.launch.model.Request;
import app.dassana.core.normalize.model.NormalizerWorkflow;
import app.dassana.core.policycontext.model.PolicyContext;
import app.dassana.core.resource.model.GeneralContext;
import app.dassana.core.resource.model.ResourceContext;
import app.dassana.core.util.StringyThings;
import app.dassana.core.workflow.WorkflowRunner;
import app.dassana.core.workflow.model.NormalizerException;
import app.dassana.core.workflow.model.Workflow;
import app.dassana.core.workflow.model.WorkflowOutputWithRisk;
import java.util.LinkedList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletionService;
import java.util.concurrent.ExecutorCompletionService;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import javax.inject.Inject;
import javax.inject.Singleton;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.utils.StringUtils;


/**
 * This is the most important class- it is responsible for processing alert end to end.
 */
@Singleton
public class RequestProcessor {

  @Inject private SqsClient sqsClient;
  @Inject private WorkflowRunner workflowRunner;
  @Inject private ContentManagerApi contentManagerApi;
  @Inject private Decorator decorator;
  @Inject private PostProcessor postProcessor;
  @Inject private S3Manager s3Manager;

  int cores = Runtime.getRuntime().availableProcessors();
  ExecutorService executorService = Executors.newFixedThreadPool(cores);
  CompletionService<Optional<WorkflowOutputWithRisk>> executorCompletionService = new ExecutorCompletionService<>(
      executorService);

  private static final Logger logger = LoggerFactory.getLogger(RequestProcessor.class);


  /**
   * This method is the actual processor of alerts. It is completely free of how the alert has been sent to Dassana.
   * Currently, this handler is hooked to two entry points - the API endpoint which is used for debugging and one hooked
   * to sqs reader. Make sure that this method remains free how the alert was sent to Dassana
   *
   * @param request this object represents the encapsulated alert.
   * @return Processing response which currently has only one String member - decoratedJson. This JSON is essentially
   * the original alert sent in the {@link Request#getInputJson()} decorated with the "dassana" object which represents
   * everything Dassana did
   * @throws Exception in case of any error thrown by downstream components. Currently, we do not handle downstream
   *                   exceptions so if there is any error in any phase- be it normalization, resource prioritization,
   *                   contextualization etc, we throw the exception. It is the responsibility of the alert ingestion
   *                   component to handle exceptions. For example, in case of API endpoint {@link ApiHandler}, we set
   *                   the status code to 500. In case of SQS handler {@link SqsHandler}, we send the alert to dead
   *                   letter queue
   */
  public ProcessingResponse processRequest(final Request request) throws Exception {

    ProcessingResponse processingResponse = new ProcessingResponse();

    logger.info("Processing input {}", StringyThings.removeNewLines(request.getInputJson()));

    Optional<WorkflowOutputWithRisk> normalizationResult;
    Optional<WorkflowOutputWithRisk> policyContext = Optional.empty();
    Optional<WorkflowOutputWithRisk> resourceContext = Optional.empty();
    Optional<WorkflowOutputWithRisk> generalContext = Optional.empty();

    normalizationResult = workflowRunner
        .runWorkFlow(NormalizerWorkflow.class, request, "");

    List<Future<Optional<WorkflowOutputWithRisk>>> futureList = new LinkedList<>();

    //if normalization is done, we run the resource prioritization and contextualization in parallel

    if (normalizationResult.isPresent()) {
      WorkflowOutputWithRisk normalizedWorkflowOutput = normalizationResult.get();
      validateNormalizerOutput(normalizedWorkflowOutput);

      String normalizedWorkflowJsonStr = new JSONObject(normalizedWorkflowOutput.getOutput()).toString();

      if (!request.isSkipGeneralContext()) {
        futureList.add(executorCompletionService
            .submit(() ->
                workflowRunner
                    .runWorkFlow(GeneralContext.class, request, normalizedWorkflowJsonStr)));
      }
      if (!request.isSkipResourceContext()) {
        futureList.add(executorCompletionService
            .submit(() ->
                workflowRunner
                    .runWorkFlow(ResourceContext.class, request, normalizedWorkflowJsonStr)));
      }

      if (!request.isSkipPolicyContext()) {
        futureList.add(executorCompletionService
            .submit(() ->
                workflowRunner
                    .runWorkFlow(PolicyContext.class, request, normalizedWorkflowJsonStr)));
      }

      for (Future<Optional<WorkflowOutputWithRisk>> ignored : futureList) {

        Optional<WorkflowOutputWithRisk> workflowOutputWithRisk = executorCompletionService.take().get();

        if (workflowOutputWithRisk.isPresent()) {
          String workflowId = workflowOutputWithRisk.get().getWorkflowId();
          for (Workflow workflow : contentManagerApi.getWorkflowSet(request)) {
            if (workflow.getId().contentEquals(workflowId)) {
              if (workflow.getType().contentEquals(POLICY_CONTEXT)) {
                policyContext = workflowOutputWithRisk;
              } else if (workflow.getType().contentEquals(GENERAL_CONTEXT)) {
                generalContext = workflowOutputWithRisk;
              } else if (workflow.getType().contentEquals(RESOURCE_CONTEXT)) {
                resourceContext = workflowOutputWithRisk;
              }
            }
          }

        }
      }

      String dassanaDecoratedJson =
          decorator.getDassanaDecoratedJson(request,
              normalizationResult.get(),
              policyContext,
              resourceContext,
              generalContext);

      //after alerts have been processed we upload the alert to a
      // s3 bucket. This allows any post processors to access the fully decorated json object.
      String decoratedJsonWithS3key = s3Manager.uploadedToS3(normalizationResult, dassanaDecoratedJson);
      String finalJson = postProcessor
          .handlePostProcessor(request, normalizationResult.get(), decoratedJsonWithS3key);

      processingResponse.setDecoratedJson(finalJson);

    } else {//normalization did not happen
      processingResponse.setNormalizerWorkflow(null);
      s3Manager.uploadedToS3(normalizationResult, request.getInputJson());
      processingResponse.setDecoratedJson(request.getInputJson());
    }

    return processingResponse;

  }

  //just a basic test for now
  //todo: use schema based validation and also perform deep validation where even values are tested.
  private void validateNormalizerOutput(WorkflowOutputWithRisk normalizerOutput) {

    checkArgsToBeTrue("vendorId", normalizerOutput);
    checkArgsToBeTrue("alertId", normalizerOutput);
    //checkArgsToBeTrue("canonicalId", normalizerOutput);
    checkArgsToBeTrue("vendorPolicy", normalizerOutput);
    checkArgsToBeTrue("csp", normalizerOutput);
    checkArgsToBeTrue("resourceContainer", normalizerOutput);
    checkArgsToBeTrue("region", normalizerOutput);
    checkArgsToBeTrue("resourceId", normalizerOutput);
  }


  private void checkArgsToBeTrue(String key, WorkflowOutputWithRisk normalizerOutput) {

    try {
      if (StringUtils.isEmpty((CharSequence) normalizerOutput.getOutput().get(key))) {
        NormalizerException normalizerException = new NormalizerException(
            String.format("%s is expected to be not empty", key));
        normalizerException.setWorkflowId(normalizerOutput.getWorkflowId());

        //relax the requirements for resource-type for now
        if (!key.contentEquals("resourceType")) {
          throw normalizerException;
        }
      }
    } catch (NullPointerException exception) {
      NormalizerException normalizerException = new NormalizerException(
          String.format("%s is expected to be not null", key));
      normalizerException.setWorkflowId(normalizerOutput.getWorkflowId());
      throw normalizerException;
    }

  }

}
