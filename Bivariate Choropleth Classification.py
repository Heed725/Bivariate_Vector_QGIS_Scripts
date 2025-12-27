"""
QGIS Processing Script: Bivariate Choropleth Map Generator
Creates a bivariate choropleth classification based on two variables
Following the methodology from Joshua Stevens' tutorial
"""

from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterField,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingException,
                       QgsField, QgsFields,
                       QgsFeature, QgsFeatureSink,
                       QgsExpression, QgsExpressionContext,
                       QgsExpressionContextUtils)
from qgis.PyQt.QtCore import QVariant
import processing


class BivariateChoroplethAlgorithm(QgsProcessingAlgorithm):
    """
    Creates bivariate classification fields for choropleth mapping
    """
    
    INPUT = 'INPUT'
    VAR1_FIELD = 'VAR1_FIELD'
    VAR2_FIELD = 'VAR2_FIELD'
    CLASSIFICATION_METHOD = 'CLASSIFICATION_METHOD'
    OUTPUT = 'OUTPUT'
    
    def initAlgorithm(self, config=None):
        # Input vector layer
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                'Input layer',
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        
        # First variable field
        self.addParameter(
            QgsProcessingParameterField(
                self.VAR1_FIELD,
                'Variable 1 (Vertical axis - numbers 1-3)',
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.Numeric
            )
        )
        
        # Second variable field
        self.addParameter(
            QgsProcessingParameterField(
                self.VAR2_FIELD,
                'Variable 2 (Horizontal axis - letters A-C)',
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.Numeric
            )
        )
        
        # Classification method
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CLASSIFICATION_METHOD,
                'Classification method',
                options=['Quantile (Equal Count)', 'Natural Breaks (Jenks)', 'Equal Interval'],
                defaultValue=0
            )
        )
        
        # Output layer
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'Output layer with bivariate classes'
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        # Get parameters
        source = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        var1_field = self.parameterAsString(parameters, self.VAR1_FIELD, context)
        var2_field = self.parameterAsString(parameters, self.VAR2_FIELD, context)
        classification_method = self.parameterAsEnum(parameters, self.CLASSIFICATION_METHOD, context)
        
        if source is None:
            raise QgsProcessingException('Invalid input layer')
        
        feedback.pushInfo(f'Processing bivariate classification...')
        feedback.pushInfo(f'Variable 1: {var1_field}')
        feedback.pushInfo(f'Variable 2: {var2_field}')
        
        # Get all values for both variables
        var1_values = []
        var2_values = []
        
        for feature in source.getFeatures():
            val1 = feature[var1_field]
            val2 = feature[var2_field]
            
            if val1 is not None:
                try:
                    var1_values.append(float(val1))
                except (ValueError, TypeError):
                    pass
            if val2 is not None:
                try:
                    var2_values.append(float(val2))
                except (ValueError, TypeError):
                    pass
        
        if not var1_values or not var2_values:
            raise QgsProcessingException('No valid values found in selected fields')
        
        # Calculate breakpoints based on classification method
        var1_breaks = self.calculate_breaks(var1_values, classification_method, feedback)
        var2_breaks = self.calculate_breaks(var2_values, classification_method, feedback)
        
        feedback.pushInfo(f'\nVariable 1 breakpoints: {var1_breaks}')
        feedback.pushInfo(f'Variable 2 breakpoints: {var2_breaks}')
        
        # Create output fields
        fields = source.fields()
        fields.append(QgsField('Var1_Class', QVariant.Int))
        fields.append(QgsField('Var2_Class', QVariant.String))
        fields.append(QgsField('Bi_Class', QVariant.String))
        
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields, source.wkbType(), source.sourceCrs()
        )
        
        if sink is None:
            raise QgsProcessingException('Could not create output layer')
        
        # Process features
        total = source.featureCount()
        for current, feature in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            
            # Get values
            val1 = feature[var1_field]
            val2 = feature[var2_field]
            
            # Classify Variable 1 (1-3, vertical)
            try:
                val1_float = float(val1) if val1 is not None else float('-inf')
            except (ValueError, TypeError):
                val1_float = float('-inf')
                
            if val1_float > var1_breaks[1]:
                var1_class = 3
            elif val1_float > var1_breaks[0]:
                var1_class = 2
            else:
                var1_class = 1
            
            # Classify Variable 2 (A-C, horizontal)
            try:
                val2_float = float(val2) if val2 is not None else float('-inf')
            except (ValueError, TypeError):
                val2_float = float('-inf')
                
            if val2_float > var2_breaks[1]:
                var2_class = 'C'
            elif val2_float > var2_breaks[0]:
                var2_class = 'B'
            else:
                var2_class = 'A'
            
            # Combine into bivariate class
            bi_class = f'{var2_class}{var1_class}'
            
            # Create output feature
            out_feature = QgsFeature(fields)
            out_feature.setGeometry(feature.geometry())
            
            # Copy attributes
            for i, field in enumerate(source.fields()):
                out_feature.setAttribute(field.name(), feature[field.name()])
            
            # Add new attributes
            out_feature.setAttribute('Var1_Class', var1_class)
            out_feature.setAttribute('Var2_Class', var2_class)
            out_feature.setAttribute('Bi_Class', bi_class)
            
            sink.addFeature(out_feature, QgsFeatureSink.FastInsert)
            
            feedback.setProgress(int(current * 100 / total))
        
        feedback.pushInfo('\nBivariate classes created:')
        feedback.pushInfo('  A1 = Low Variable 2, Low Variable 1')
        feedback.pushInfo('  A2 = Low Variable 2, Medium Variable 1')
        feedback.pushInfo('  A3 = Low Variable 2, High Variable 1')
        feedback.pushInfo('  B1 = Medium Variable 2, Low Variable 1')
        feedback.pushInfo('  B2 = Medium Variable 2, Medium Variable 1')
        feedback.pushInfo('  B3 = Medium Variable 2, High Variable 1')
        feedback.pushInfo('  C1 = High Variable 2, Low Variable 1')
        feedback.pushInfo('  C2 = High Variable 2, Medium Variable 1')
        feedback.pushInfo('  C3 = High Variable 2, High Variable 1')
        feedback.pushInfo('\nUse "Bi_Class" field for categorized symbology')
        
        return {self.OUTPUT: dest_id}
    
    def calculate_breaks(self, values, method, feedback):
        """
        Calculate classification breakpoints for 3 classes
        Returns two breakpoints [lower, upper]
        """
        values_sorted = sorted(values)
        n = len(values_sorted)
        
        if method == 0:  # Quantile
            # Equal count: divide into thirds
            lower_break = values_sorted[n // 3]
            upper_break = values_sorted[(2 * n) // 3]
            
        elif method == 1:  # Natural Breaks (simplified Jenks)
            # Use approximate Jenks breaks
            lower_break = self.jenks_break(values_sorted, 0.33)
            upper_break = self.jenks_break(values_sorted, 0.67)
            
        else:  # Equal Interval
            min_val = min(values)
            max_val = max(values)
            interval = (max_val - min_val) / 3
            lower_break = min_val + interval
            upper_break = min_val + (2 * interval)
        
        return [lower_break, upper_break]
    
    def jenks_break(self, sorted_values, percentile):
        """
        Simplified natural breaks calculation
        """
        idx = int(len(sorted_values) * percentile)
        return sorted_values[min(idx, len(sorted_values) - 1)]
    
    def name(self):
        return 'bivariatechoropleth'
    
    def displayName(self):
        return 'Bivariate Choropleth Classification'
    
    def group(self):
        return 'Cartography'
    
    def groupId(self):
        return 'cartography'
    
    def shortHelpString(self):
        return """
        Creates a bivariate choropleth classification for two numeric variables.
        
        This algorithm classifies two variables into 3 classes each and combines them
        into a 9-class bivariate classification scheme (A1-C3).
        
        Variable 1 is classified vertically (1-3, low to high)
        Variable 2 is classified horizontally (A-C, low to high)
        
        The output includes three new fields:
        - Var1_Class: Integer 1-3
        - Var2_Class: String A-C
        - Bi_Class: Combined classification (e.g., "A1", "B2", "C3")
        
        Use the Bi_Class field with categorized symbology to create your bivariate map.
        
        Recommended color scheme:
        - Variable 1: Purple (light to dark, vertical)
        - Variable 2: Orange (light to dark, horizontal)
        - C3 corner: Dark blue (both variables high)
        
        Based on methodology by Joshua Stevens:
        https://www.joshuastevens.net/cartography/make-a-bivariate-choropleth-map/
        """
    
    def createInstance(self):
        return BivariateChoroplethAlgorithm()
