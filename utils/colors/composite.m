% composite the 8 bands of a worldview 3 spectrum into rgb
% (this code fins the coefficients of the composition from the spectral curves)

% read curves
rgb = dlmread("cie31xyz.txt");
wws = dlmread("wvs_471.txt");

% extract interesting part
X = wws(:,3:9);
Y = rgb(:,2:4);

% matrices of the system
A = X'*X;
b = X'*Y;

% solve the system
C = A\b;

% visualize
%Z = X*C;
%plot([Z,Y])

% save the matrix C
dlmwrite("C.csv", C);

% print the matrix C in a plambda-friendly form
for k=[1:3];
	for i = [1:7];
		printf("x[%d] %g *\n", i-1, C(i,k));
	end;
	printf("+ + + + + +\n");
end;
printf("join3 xyz2rgb\n");
