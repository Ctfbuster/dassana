package app.dassana.core.launch;

import app.dassana.core.contentmanager.ContentManagerApi;
import app.dassana.core.launch.model.ProcessingResponse;
import app.dassana.core.launch.model.Request;
import app.dassana.core.normalize.model.NormalizerWorkflow;
import app.dassana.core.workflow.processor.RequestProcessor;
import com.amazonaws.services.lambda.runtime.events.SQSEvent;
import com.amazonaws.services.lambda.runtime.events.SQSEvent.SQSMessage;
import io.micronaut.core.annotation.Introspected;
import io.micronaut.function.aws.MicronautRequestHandler;
import java.util.List;
import javax.inject.Inject;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;

@Introspected
public class SqsHandler extends MicronautRequestHandler<SQSEvent, Void> {

  private static final Logger logger = LoggerFactory.getLogger(SqsHandler.class);

  private final String dassanaDeadLetterQueue = System.getenv("dassanaDeadLetterQueue");
  private final String dassanaOutboundQueue = System.getenv("dassanaOutboundQueue");


  @Inject private ContentManagerApi contentManager;
  @Inject private RequestProcessor requestProcessor;
  @Inject private SqsClient sqsClient;


  @Override
  public Void execute(SQSEvent input) {

    List<SQSMessage> sqsMessages = input.getRecords();

    for (SQSMessage message : sqsMessages) {
      try {
        Request request = new Request(message.getBody());

        request.setQueueProcessing(true);
        request.setSkipGeneralContext(false);
        request.setSkipPolicyContext(false);
        request.setSkipPostProcessor(false);
        request.setIncludeAlertInOutput(true);
        request.setIncludeStepOutput(true);

        ProcessingResponse processingResponse = requestProcessor.processRequest(request);
        NormalizerWorkflow normalizerWorkflow = processingResponse.getNormalizerWorkflow();

        if(normalizerWorkflow==null){
          sqsClient.sendMessage(SendMessageRequest.builder().
              queueUrl(dassanaOutboundQueue).
              messageBody(processingResponse.getDecoratedJson()).build());

        }else if (normalizerWorkflow.isOutputQueueEnabled() && request.isQueueProcessing()) {
          sqsClient.sendMessage(SendMessageRequest.builder().
              queueUrl(dassanaOutboundQueue).
              messageBody(processingResponse.getDecoratedJson()).build());
        }


      } catch (Exception e) {
        handleException(e, message.getBody());

      }


    }

    return null;

  }

  private void handleException(Exception exception, String originalInput) {

    logger.error("Error in processing message: ", exception);
    JSONObject jsonObject = new JSONObject(originalInput);
    jsonObject.put("error", exception);

    sqsClient.sendMessage(
        SendMessageRequest.builder().queueUrl(dassanaDeadLetterQueue)
            .messageBody(jsonObject.toString())
            .build());


  }


}
