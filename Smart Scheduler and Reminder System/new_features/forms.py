from django import forms
from campus.models import BookedUnit, Course
from accounts.models import Faculty

class BookedUnitForm(forms.ModelForm):
    lecturer = forms.ModelChoiceField(
        queryset=Faculty.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    course = forms.ModelChoiceField( # New ModelChoiceField for course
        queryset=Course.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = BookedUnit
        fields = ['lecturer', 'students_course', 'course', 'year_of_study', 'semester']
        widgets = {
            'students_course': forms.TextInput(attrs={'class': 'form-control'}),
            'year_of_study': forms.TextInput(attrs={'class': 'form-control'}),
            'semester': forms.TextInput(attrs={'class': 'form-control'}),
        }
