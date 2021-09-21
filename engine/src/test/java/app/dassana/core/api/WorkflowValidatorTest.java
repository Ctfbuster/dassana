package app.dassana.core.api;

import app.dassana.core.contentmanager.ContentManager;
import app.dassana.core.contentmanager.model.WorkflowProcessingResult;
import app.dassana.core.launch.model.Message;
import app.dassana.core.util.StringyThings;
import com.google.gson.Gson;
import io.micronaut.test.extensions.junit5.annotation.MicronautTest;
import java.io.File;
import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedList;
import java.util.List;
import javax.inject.Inject;
import org.apache.commons.io.FileUtils;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;

@MicronautTest
class WorkflowValidatorTest {

  @Inject WorkflowValidator workflowValidator;
  @Inject ContentManager contentManager;
  @Inject Gson gson;

  void assertFail(String errMsg, Path path){
    Assertions.fail(String.format("error in file: %s, %s", path.toFile().getName(), errMsg));
  }

  @Test
  void handleValidate() throws Exception {

    String content = Thread.currentThread().getContextClassLoader().getResource("content/workflows").getFile();
    WorkflowProcessingResult workflowProcessingResult = contentManager.processDir(new File(content));

    if (workflowProcessingResult.getWorkflowFileToExceptionMap().size() > 0) {
      List<String> workflows = new LinkedList<>();
      workflowProcessingResult.getWorkflowFileToExceptionMap().forEach((s, e) -> workflows.add(s));
      throw new DassanaWorkflowValidationException(String.format("Workflows %s aren't valid", workflows));
    }

    Files.walk(Paths.get(content))
        .filter(Files::isRegularFile)
        .forEach(path -> {
          try {
            String workflowYaml = FileUtils.readFileToString(path.toFile(), Charset.defaultCharset());

            try {
              workflowValidator.handleValidate(StringyThings.getJsonFromYaml(workflowYaml));
            } catch (Exception e) {
              if (e instanceof DassanaWorkflowValidationException) {
                DassanaWorkflowValidationException dassanaWorkflowValidationException = (DassanaWorkflowValidationException) e;
                List<Message> messages = dassanaWorkflowValidationException.getMessages();
                for (Message message : messages) {
                  assertFail(message.getMsg(), path);
                }
              } else {
                assertFail(e.getMessage(), path);
              }
            }

          } catch (IOException e) {
            Assertions.fail(e);
          }


        });


  }
}