package app.dassana.core.api.linter;

import app.dassana.core.api.ValidationException;
import app.dassana.core.contentmanager.ContentManager;
import com.google.gson.Gson;
import org.yaml.snakeyaml.Yaml;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.util.*;

import static app.dassana.core.api.linter.BaseLinter.loadFilesFromPath;

public class CommonLinter {

	private final static String actionTemplatePath = "/actions";
	private final static String[] requiredFields = new String[]{"vendorId", "alertId", "vendorPolicy", "csp", "resourceContainer",
					"region", "resourceId"};

	private Gson gson = new Gson();
	private Set<String> actions = new HashSet<>();
	private Set<String> required = new HashSet<>();
	private Yaml yaml = new Yaml();
	protected String content = Thread.currentThread().getContextClassLoader().getResource("content").getFile();

	public CommonLinter(){
		required.addAll(Arrays.asList(requiredFields));
	}

	public void init() throws FileNotFoundException {
		loadActions();
	}

	public StatusMsg validateRequiredFields(String json){
		Map<String, Object> data = gson.fromJson(json, Map.class);
		StatusMsg statusMsg = requiredFields(data);
		return statusMsg;
	}

	public void validateRequiredFields(Map<String, Object> data, String filename){
		StatusMsg statusMsg = requiredFields(data);
		if(statusMsg.isError()){
			throw new ValidationException(statusMsg.getMsg() + " in file: " + filename);
		}
	}

	private StatusMsg requiredFields(Map<String, Object> data){
		StatusMsg statusMsg = new StatusMsg(false);
		List<Map<String, Object>> outputs = (List<Map<String, Object>>) data.get(ContentManager.FIELDS.OUTPUT.getName());
		Set<String> names = new HashSet<>();
		if(outputs != null) {
			for (int i = 0; i < outputs.size(); i++) {
				Map<String, Object> output = outputs.get(i);
				names.add((String) output.get("name"));
			}
		}

		if(!names.containsAll(required) && outputs != null) {
			Set<String> requireCopy = new HashSet<>();
			requireCopy.addAll(required);
			requireCopy.removeAll(names);
			statusMsg = new StatusMsg(true, "Following required fields are missing: " + requireCopy);
		}

		return statusMsg;
	}

	private void loadActions() throws FileNotFoundException {
		List<File> files = loadFilesFromPath(content + actionTemplatePath, new String[]{"yaml"});
		for(File file : files){
			Map<String, Object> data = yaml.load(new FileInputStream(file));
			actions.add((String)data.get("id"));
		}
	}

	protected void validateSteps(Map<String, Object> data, String filename) {
		StatusMsg statusMsg = validateYaml(data);
		if(statusMsg.isError()){
			throw new ValidationException(statusMsg.getMsg() + " in file: " + filename);
		}
	}

	protected StatusMsg validateSteps(String json){
		Map<String, Object> data = gson.fromJson(json, Map.class);
		StatusMsg statusMsg = validateYaml(data);
		return statusMsg;
	}

	private StatusMsg validateYaml(Map<String, Object> data) {
		StatusMsg statusMsg = new StatusMsg(false);
		if(data.containsKey(ContentManager.FIELDS.STEPS.getName())){
			List<Map<String, Object>> steps = (List<Map<String, Object>>) data.get(ContentManager.FIELDS.STEPS.getName());
			statusMsg = checkStepsForErrors(steps);
		}
		return statusMsg;
	}

	private StatusMsg checkStepsForErrors(List<Map<String, Object>> steps){
		boolean isError = false;
		String errorMsg = null;
		for(int i = 0; i < steps.size() && !isError; i++){
			Map<String, Object> step = steps.get(i);
			if(!actions.contains(step.get(ContentManager.FIELDS.USES.getName()))){
				isError  = true;
				errorMsg = "Invalid uses field: [" +  step.get(ContentManager.FIELDS.USES.getName()) + "], " +
				"available fields: " + actions;
			}
		}
		return new StatusMsg(isError, errorMsg);
	}

}
